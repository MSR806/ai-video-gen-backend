from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.generation.finalize_generation import GenerationFinalizer
from ai_video_gen_backend.application.generation.reconcile_generation_job import (
    ReconcileGenerationJobUseCase,
)
from ai_video_gen_backend.domain.generation import (
    GeneratedOutput,
    GenerationJob,
    GenerationStatus,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
)


class FakeGenerationJobRepository:
    def __init__(
        self,
        *,
        mark_in_progress_job: GenerationJob,
        refreshed_job: GenerationJob | None,
    ) -> None:
        self.mark_in_progress_job = mark_in_progress_job
        self.refreshed_job = refreshed_job
        self.mark_in_progress_calls: list[UUID] = []
        self.get_by_id_calls: list[UUID] = []

    def create_job(
        self,
        *,
        project_id: UUID,
        collection_id: UUID,
        collection_item_id: UUID,
        operation_key: str,
        provider: str,
        model_key: str,
        endpoint_id: str,
        inputs_json: dict[str, object],
        idempotency_key: str | None,
    ) -> GenerationJob:
        del (
            project_id,
            collection_id,
            collection_item_id,
            operation_key,
            provider,
            model_key,
            endpoint_id,
            inputs_json,
            idempotency_key,
        )
        raise NotImplementedError

    def get_by_id(self, job_id: UUID) -> GenerationJob | None:
        self.get_by_id_calls.append(job_id)
        return self.refreshed_job

    def get_by_provider_request_id(self, provider_request_id: str) -> GenerationJob | None:
        del provider_request_id
        return None

    def get_by_idempotency_key(
        self,
        *,
        project_id: UUID,
        collection_id: UUID,
        idempotency_key: str,
    ) -> GenerationJob | None:
        del project_id, collection_id, idempotency_key
        return None

    def mark_submitted(self, job_id: UUID, *, provider_request_id: str) -> GenerationJob:
        del job_id, provider_request_id
        raise NotImplementedError

    def mark_in_progress(self, job_id: UUID) -> GenerationJob:
        self.mark_in_progress_calls.append(job_id)
        return self.mark_in_progress_job

    def mark_succeeded(
        self,
        job_id: UUID,
        *,
        provider_response_json: dict[str, object],
        outputs_json: list[dict[str, object]],
    ) -> GenerationJob:
        del job_id, provider_response_json, outputs_json
        raise NotImplementedError

    def mark_failed(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationJob:
        del job_id, error_code, error_message, provider_response_json
        raise NotImplementedError


class FakeGenerationProvider:
    def __init__(self, *, status: ProviderStatus, result: ProviderResult) -> None:
        self.status_value = status
        self.result_value = result
        self.status_calls: list[tuple[str, str]] = []
        self.result_calls: list[tuple[str, str]] = []

    def submit(
        self,
        *,
        endpoint_id: str,
        inputs: dict[str, object],
        webhook_url: str,
    ) -> ProviderSubmission:
        del endpoint_id, inputs, webhook_url
        raise NotImplementedError

    def status(self, *, endpoint_id: str, provider_request_id: str) -> ProviderStatus:
        self.status_calls.append((endpoint_id, provider_request_id))
        return self.status_value

    def result(self, *, endpoint_id: str, provider_request_id: str) -> ProviderResult:
        self.result_calls.append((endpoint_id, provider_request_id))
        return self.result_value

    def cancel(self, *, endpoint_id: str, provider_request_id: str) -> None:
        del endpoint_id, provider_request_id

    def parse_webhook(self, payload: dict[str, object]) -> ProviderWebhookEvent | None:
        del payload
        return None


class FakeGenerationFinalizer:
    def __init__(self) -> None:
        self.success_calls: list[dict[str, object]] = []
        self.failure_calls: list[dict[str, object]] = []

    def finalize_success(
        self,
        *,
        job_id: UUID,
        item_id: UUID,
        output: dict[str, object],
        provider_response_json: dict[str, object],
        outputs_json: list[dict[str, object]],
    ) -> None:
        self.success_calls.append(
            {
                'job_id': job_id,
                'item_id': item_id,
                'output': output,
                'provider_response_json': provider_response_json,
                'outputs_json': outputs_json,
            }
        )

    def finalize_failure(
        self,
        *,
        job_id: UUID,
        item_id: UUID,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> None:
        self.failure_calls.append(
            {
                'job_id': job_id,
                'item_id': item_id,
                'error_code': error_code,
                'error_message': error_message,
                'provider_response_json': provider_response_json,
            }
        )


def _job_fixture(
    *,
    status: GenerationStatus = 'IN_PROGRESS',
    with_provider_request_id: bool = True,
    with_endpoint_id: bool = True,
    with_item_id: bool = True,
) -> GenerationJob:
    now = datetime.now(UTC)
    return GenerationJob(
        id=uuid4(),
        project_id=uuid4(),
        collection_id=uuid4(),
        collection_item_id=uuid4() if with_item_id else None,
        operation_key='text_to_image',
        provider='fal',
        model_key='nano_banana',
        endpoint_id='fal-ai/nano-banana' if with_endpoint_id else None,
        status=status,
        inputs_json={'prompt': 'cat'},
        outputs_json=[],
        provider_request_id='req-123' if with_provider_request_id else None,
        provider_response_json=None,
        idempotency_key=None,
        error_code=None,
        error_message=None,
        submitted_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


def _provider_result(
    *,
    status: Literal['SUCCEEDED', 'FAILED'],
    outputs: list[GeneratedOutput] | None = None,
    error_message: str | None = None,
) -> ProviderResult:
    return ProviderResult(
        status=status,
        outputs=outputs or [],
        raw_response={'status': status},
        error_message=error_message,
    )


def _build_use_case(
    repository: FakeGenerationJobRepository,
    provider: FakeGenerationProvider,
    finalizer: FakeGenerationFinalizer,
) -> ReconcileGenerationJobUseCase:
    return ReconcileGenerationJobUseCase(repository, provider, cast(GenerationFinalizer, finalizer))


@pytest.mark.parametrize('terminal_status', ['SUCCEEDED', 'FAILED', 'CANCELLED'])
def test_execute_short_circuits_terminal_jobs(
    terminal_status: Literal['SUCCEEDED', 'FAILED', 'CANCELLED'],
) -> None:
    job = _job_fixture(status=terminal_status)
    provider = FakeGenerationProvider(
        status=ProviderStatus(status='IN_PROGRESS'),
        result=_provider_result(status='FAILED'),
    )
    repository = FakeGenerationJobRepository(mark_in_progress_job=job, refreshed_job=job)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    result = use_case.execute(job)

    assert result == job
    assert provider.status_calls == []
    assert provider.result_calls == []


def test_execute_short_circuits_when_provider_request_id_is_missing() -> None:
    job = _job_fixture(with_provider_request_id=False)
    provider = FakeGenerationProvider(
        status=ProviderStatus(status='IN_PROGRESS'),
        result=_provider_result(status='FAILED'),
    )
    repository = FakeGenerationJobRepository(mark_in_progress_job=job, refreshed_job=job)
    use_case = _build_use_case(repository, provider, FakeGenerationFinalizer())

    result = use_case.execute(job)

    assert result == job
    assert provider.status_calls == []


def test_execute_short_circuits_when_endpoint_id_is_missing() -> None:
    job = _job_fixture(with_endpoint_id=False)
    provider = FakeGenerationProvider(
        status=ProviderStatus(status='IN_PROGRESS'),
        result=_provider_result(status='FAILED'),
    )
    repository = FakeGenerationJobRepository(mark_in_progress_job=job, refreshed_job=job)
    use_case = _build_use_case(repository, provider, FakeGenerationFinalizer())

    result = use_case.execute(job)

    assert result == job
    assert provider.status_calls == []


def test_execute_marks_job_in_progress_when_provider_reports_in_progress() -> None:
    job = _job_fixture()
    in_progress_job = _job_fixture(status='IN_PROGRESS')
    provider = FakeGenerationProvider(
        status=ProviderStatus(status='IN_PROGRESS'),
        result=_provider_result(status='FAILED'),
    )
    repository = FakeGenerationJobRepository(
        mark_in_progress_job=in_progress_job,
        refreshed_job=in_progress_job,
    )
    use_case = _build_use_case(repository, provider, FakeGenerationFinalizer())

    result = use_case.execute(job)

    assert result == in_progress_job
    assert provider.status_calls == [('fal-ai/nano-banana', 'req-123')]
    assert repository.mark_in_progress_calls == [job.id]


@pytest.mark.parametrize(
    'status_value',
    ['FAILED', 'CANCELLED'],
)
def test_execute_finalizes_failure_when_provider_status_is_failed_or_cancelled(
    status_value: Literal['FAILED', 'CANCELLED'],
) -> None:
    job = _job_fixture(with_item_id=True)
    refreshed = _job_fixture(status='FAILED', with_item_id=True)
    provider = FakeGenerationProvider(
        status=ProviderStatus(status=status_value),
        result=_provider_result(status='FAILED'),
    )
    repository = FakeGenerationJobRepository(mark_in_progress_job=job, refreshed_job=refreshed)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    result = use_case.execute(job)

    assert result == refreshed
    assert len(finalizer.failure_calls) == 1
    assert finalizer.failure_calls[0]['job_id'] == job.id
    assert finalizer.failure_calls[0]['error_message'] == 'Generation failed on provider'
    assert repository.get_by_id_calls == [job.id]


def test_execute_skips_finalize_failure_for_status_failed_when_collection_item_missing() -> None:
    job = _job_fixture(with_item_id=False)
    provider = FakeGenerationProvider(
        status=ProviderStatus(status='FAILED'),
        result=_provider_result(status='FAILED'),
    )
    repository = FakeGenerationJobRepository(mark_in_progress_job=job, refreshed_job=None)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    result = use_case.execute(job)

    assert result == job
    assert finalizer.failure_calls == []


def test_execute_finalizes_success_when_result_has_outputs() -> None:
    job = _job_fixture(with_item_id=True)
    refreshed = _job_fixture(status='SUCCEEDED', with_item_id=True)
    provider = FakeGenerationProvider(
        status=ProviderStatus(status='SUCCEEDED'),
        result=_provider_result(
            status='SUCCEEDED',
            outputs=[
                GeneratedOutput(
                    index=0,
                    media_type='image',
                    provider_url='https://provider.test/image.png',
                    metadata={'seed': 42},
                )
            ],
        ),
    )
    repository = FakeGenerationJobRepository(mark_in_progress_job=job, refreshed_job=refreshed)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    result = use_case.execute(job)

    assert result == refreshed
    assert provider.result_calls == [('fal-ai/nano-banana', 'req-123')]
    assert len(finalizer.success_calls) == 1
    assert finalizer.success_calls[0]['job_id'] == job.id
    assert repository.get_by_id_calls == [job.id]


def test_execute_finalizes_failure_when_result_succeeds_without_outputs() -> None:
    job = _job_fixture(with_item_id=True)
    provider = FakeGenerationProvider(
        status=ProviderStatus(status='SUCCEEDED'),
        result=_provider_result(status='SUCCEEDED', outputs=[]),
    )
    repository = FakeGenerationJobRepository(mark_in_progress_job=job, refreshed_job=job)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    use_case.execute(job)

    assert len(finalizer.failure_calls) == 1
    assert finalizer.failure_calls[0]['error_message'] == 'Generation failed on provider'


def test_execute_finalizes_failure_when_result_failed_and_uses_provider_message() -> None:
    job = _job_fixture(with_item_id=True)
    provider = FakeGenerationProvider(
        status=ProviderStatus(status='SUCCEEDED'),
        result=_provider_result(
            status='FAILED',
            outputs=[],
            error_message='provider timeout',
        ),
    )
    repository = FakeGenerationJobRepository(mark_in_progress_job=job, refreshed_job=job)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    use_case.execute(job)

    assert len(finalizer.failure_calls) == 1
    assert finalizer.failure_calls[0]['error_message'] == 'provider timeout'


def test_execute_returns_original_job_when_refreshed_job_is_missing() -> None:
    job = _job_fixture(with_item_id=True)
    provider = FakeGenerationProvider(
        status=ProviderStatus(status='SUCCEEDED'),
        result=_provider_result(status='FAILED'),
    )
    repository = FakeGenerationJobRepository(mark_in_progress_job=job, refreshed_job=None)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    result = use_case.execute(job)

    assert result == job
    assert len(finalizer.failure_calls) == 1
