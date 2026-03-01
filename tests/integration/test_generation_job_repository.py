from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from ai_video_gen_backend.infrastructure.db.models import (
    CollectionItemModel,
    CollectionModel,
    ProjectModel,
)
from ai_video_gen_backend.infrastructure.repositories import GenerationJobSqlRepository


def test_generation_job_repository_lifecycle(db_session: Session) -> None:
    project_id = uuid4()
    collection_id = uuid4()
    item_id = uuid4()

    db_session.add(
        ProjectModel(
            id=project_id,
            name='Project',
            description='Generation project',
            status='draft',
        )
    )
    db_session.add(
        CollectionModel(
            id=collection_id,
            project_id=project_id,
            name='Collection',
            tag='ref',
            description='Generation collection',
        )
    )
    db_session.add(
        CollectionItemModel(
            id=item_id,
            project_id=project_id,
            collection_id=collection_id,
            media_type='image',
            status='GENERATING',
            name='Placeholder',
            description='Pending generation',
            url=None,
            metadata_json={'thumbnailUrl': '', 'width': 0, 'height': 0, 'format': 'png'},
            generation_source='fal',
        )
    )
    db_session.commit()

    repository = GenerationJobSqlRepository(db_session)
    created = repository.create_job(
        project_id=project_id,
        collection_id=collection_id,
        collection_item_id=item_id,
        operation='TEXT_TO_IMAGE',
        provider='fal',
        model_key='nano_banana_t2i_v1',
        request_payload={'prompt': 'cat'},
    )

    assert created.status == 'QUEUED'

    submitted = repository.mark_submitted(
        created.id,
        provider_request_id='req-123',
    )
    assert submitted.status == 'IN_PROGRESS'
    assert submitted.provider_request_id == 'req-123'

    succeeded = repository.mark_succeeded(
        created.id,
        provider_response={'images': [{'url': 'https://example.com/image.png'}]},
    )
    assert succeeded.status == 'SUCCEEDED'
    assert succeeded.provider_response is not None


def test_generation_job_repository_marks_failed(db_session: Session) -> None:
    project_id = uuid4()
    collection_id = uuid4()
    item_id = uuid4()

    db_session.add(
        ProjectModel(
            id=project_id,
            name='Project',
            description='Generation project',
            status='draft',
        )
    )
    db_session.add(
        CollectionModel(
            id=collection_id,
            project_id=project_id,
            name='Collection',
            tag='ref',
            description='Generation collection',
        )
    )
    db_session.add(
        CollectionItemModel(
            id=item_id,
            project_id=project_id,
            collection_id=collection_id,
            media_type='image',
            status='GENERATING',
            name='Placeholder',
            description='Pending generation',
            url=None,
            metadata_json={'thumbnailUrl': '', 'width': 0, 'height': 0, 'format': 'png'},
            generation_source='fal',
        )
    )
    db_session.commit()

    repository = GenerationJobSqlRepository(db_session)
    created = repository.create_job(
        project_id=project_id,
        collection_id=collection_id,
        collection_item_id=item_id,
        operation='IMAGE_TO_IMAGE',
        provider='fal',
        model_key='nano_banana_i2i_v1',
        request_payload={'prompt': 'cat'},
    )

    failed = repository.mark_failed(
        created.id,
        error_code='provider_failed',
        error_message='provider failed',
    )
    assert failed.status == 'FAILED'
    assert failed.error_code == 'provider_failed'
