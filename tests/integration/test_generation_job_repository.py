from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from ai_video_gen_backend.infrastructure.db.models import (
    ProjectModel,
)
from ai_video_gen_backend.infrastructure.repositories import GenerationRunSqlRepository


def test_generation_run_repository_lifecycle(db_session: Session) -> None:
    project_id = uuid4()

    db_session.add(
        ProjectModel(
            id=project_id,
            name='Project',
            description='Generation project',
            status='draft',
        )
    )
    db_session.commit()

    repository = GenerationRunSqlRepository(db_session)
    created = repository.create_run(
        project_id=project_id,
        operation_key='text_to_image',
        provider='fal',
        model_key='nano_banana',
        endpoint_id='fal-ai/nano-banana',
        requested_output_count=2,
        inputs_json={'prompt': 'cat'},
        idempotency_key='idem-1',
    )

    assert created.status == 'QUEUED'
    assert created.operation_key == 'text_to_image'
    assert created.requested_output_count == 2
    assert created.endpoint_id == 'fal-ai/nano-banana'

    fetched_by_idempotency = repository.get_run_by_idempotency_key(
        project_id=project_id,
        idempotency_key='idem-1',
    )
    assert fetched_by_idempotency is not None
    assert fetched_by_idempotency.id == created.id

    created_outputs = repository.create_run_outputs(run_id=created.id, output_count=2)
    assert [output.output_index for output in created_outputs] == [0, 1]

    submitted = repository.mark_run_submitted(
        created.id,
        provider_request_id='req-123',
    )
    assert submitted.status == 'IN_PROGRESS'
    assert submitted.provider_request_id == 'req-123'

    ready_output = repository.mark_output_ready(
        output_id=created_outputs[0].id,
        provider_output_json={'index': 0, 'provider_url': 'https://provider.test/0.png'},
        stored_output_json={'storedUrl': 'https://cdn.test/0.png'},
    )
    assert ready_output.status == 'READY'

    failed_output = repository.mark_output_failed(
        output_id=created_outputs[1].id,
        error_code='provider_generation_failed',
        error_message='provider failed',
    )
    assert failed_output.status == 'FAILED'

    partial = repository.mark_run_partial_failed(
        created.id,
        provider_response_json={'images': [{'url': 'https://example.com/image.png'}]},
        error_message='Some outputs failed',
    )
    assert partial.status == 'PARTIAL_FAILED'
    assert partial.provider_response_json is not None
    assert partial.error_code == 'partial_failed'


def test_generation_run_repository_marks_failed_and_cancelled(db_session: Session) -> None:
    project_id = uuid4()

    db_session.add(
        ProjectModel(
            id=project_id,
            name='Project',
            description='Generation project',
            status='draft',
        )
    )
    db_session.commit()

    repository = GenerationRunSqlRepository(db_session)
    created = repository.create_run(
        project_id=project_id,
        operation_key='image_to_image',
        provider='fal',
        model_key='nano_banana',
        endpoint_id='fal-ai/nano-banana/edit',
        requested_output_count=1,
        inputs_json={'prompt': 'cat'},
        idempotency_key=None,
    )

    failed = repository.mark_run_failed(
        created.id,
        error_code='provider_failed',
        error_message='provider failed',
    )
    assert failed.status == 'FAILED'
    assert failed.error_code == 'provider_failed'

    cancelled = repository.mark_run_cancelled(
        created.id,
        error_message='cancelled by provider',
    )
    assert cancelled.status == 'CANCELLED'
    assert cancelled.error_code == 'cancelled'
