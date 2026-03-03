from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.generation.finalize_generation import (
    GenerationFinalizationError,
)
from ai_video_gen_backend.application.generation.get_generation_job import GetGenerationJobUseCase
from ai_video_gen_backend.application.generation.handle_fal_webhook import HandleFalWebhookUseCase
from ai_video_gen_backend.application.generation.reconcile_generation_job import (
    ReconcileGenerationJobUseCase,
)
from ai_video_gen_backend.domain.generation import GenerationJob, ProviderResult, ProviderStatus


class FakeGenerationJobRepository:
    def __init__(self, job: GenerationJob | None) -> None:
        self.job = job
        self.marked_in_progress_job_id: UUID | None = None
        self.get_by_id_calls: int = 0

    def get_by_id(self, job_id: UUID) -> GenerationJob | None:
        self.get_by_id_calls += 1
        if self.job is not None and self.job.id == job_id:
            return self.job
        return None

    def get_by_provider_request_id(self, provider_request_id: str) -> GenerationJob | None:
        if self.job is not None and self.job.provider_request_id == provider_request_id:
            return self.job
        return None

    def mark_in_progress(self, job_id: UUID) -> GenerationJob:
        self.marked_in_progress_job_id = job_id
        assert self.job is not None
        return self.job


class FakeGenerationProvider:
    def __init__(self) -> None:
        self.webhook_event: object | None = None
        self.result_value: ProviderResult = ProviderResult(
            status='FAILED',
            output_url=None,
            raw_response={'status': 'FAILED'},
            error_message='failed',
        )
        self.status_value: ProviderStatus = ProviderStatus(status='IN_PROGRESS')

    def parse_webhook(self, payload: dict[str, object]) -> object | None:
        del payload
        return self.webhook_event

    def result(self, *, model_key: str, provider_request_id: str) -> ProviderResult:
        del model_key, provider_request_id
        return self.result_value

    def status(self, *, model_key: str, provider_request_id: str) -> ProviderStatus:
        del model_key, provider_request_id
        return self.status_value


class FakeGenerationFinalizer:
    def __init__(self) -> None:
        self.success_calls: list[dict[str, object]] = []
        self.failure_calls: list[dict[str, object]] = []

    def finalize_success(self, **kwargs: object) -> None:
        self.success_calls.append(kwargs)

    def finalize_failure(self, **kwargs: object) -> None:
        self.failure_calls.append(kwargs)


class FakeReconcileUseCase:
    def __init__(self, returned_job: GenerationJob) -> None:
        self.returned_job = returned_job
        self.called_with: GenerationJob | None = None

    def execute(self, job: GenerationJob) -> GenerationJob:
        self.called_with = job
        return self.returned_job


def _job(
    *,
    status: str = 'IN_PROGRESS',
    provider_request_id: str | None = 'req-1',
    collection_item_id: UUID | None = None,
    updated_at: datetime | None = None,
) -> GenerationJob:
    now = datetime.now(UTC)
    return GenerationJob(
        id=uuid4(),
        project_id=uuid4(),
        collection_id=uuid4(),
        collection_item_id=collection_item_id,
        operation='TEXT_TO_IMAGE',
        provider='fal',
        model_key='nano_banana_t2i_v1',
        status=status,  # type: ignore[arg-type]
        request_payload={'prompt': 'hello'},
        provider_request_id=provider_request_id,
        provider_response=None,
        error_code=None,
        error_message=None,
        submitted_at=now,
        completed_at=None,
        created_at=now,
        updated_at=updated_at or now,
    )


def test_get_generation_job_returns_none_when_missing() -> None:
    repository = FakeGenerationJobRepository(job=None)
    returned = _job()
    reconcile = FakeReconcileUseCase(returned)
    use_case = GetGenerationJobUseCase(repository, reconcile, reconcile_after_seconds=30)

    result = use_case.execute(uuid4())

    assert result is None
    assert reconcile.called_with is None


def test_get_generation_job_skips_reconcile_for_terminal_status() -> None:
    existing = _job(status='SUCCEEDED')
    repository = FakeGenerationJobRepository(job=existing)
    reconcile = FakeReconcileUseCase(existing)
    use_case = GetGenerationJobUseCase(repository, reconcile, reconcile_after_seconds=30)

    result = use_case.execute(existing.id)

    assert result == existing
    assert reconcile.called_with is None


def test_get_generation_job_skips_reconcile_for_recent_update() -> None:
    existing = _job(updated_at=datetime.now(UTC) - timedelta(seconds=10))
    repository = FakeGenerationJobRepository(job=existing)
    reconcile = FakeReconcileUseCase(_job())
    use_case = GetGenerationJobUseCase(repository, reconcile, reconcile_after_seconds=30)

    result = use_case.execute(existing.id)

    assert result == existing
    assert reconcile.called_with is None


def test_get_generation_job_reconciles_stale_job() -> None:
    existing = _job(updated_at=datetime.now(UTC) - timedelta(seconds=300))
    refreshed = _job(status='SUCCEEDED', updated_at=datetime.now(UTC))
    repository = FakeGenerationJobRepository(job=existing)
    reconcile = FakeReconcileUseCase(refreshed)
    use_case = GetGenerationJobUseCase(repository, reconcile, reconcile_after_seconds=30)

    result = use_case.execute(existing.id)

    assert reconcile.called_with == existing
    assert result == refreshed


def test_handle_fal_webhook_ignores_unknown_event() -> None:
    job = _job(collection_item_id=uuid4())
    repository = FakeGenerationJobRepository(job=job)
    provider = FakeGenerationProvider()
    provider.webhook_event = None
    finalizer = FakeGenerationFinalizer()

    use_case = HandleFalWebhookUseCase(repository, provider, finalizer)

    assert use_case.execute({'type': 'unknown'}) is False
    assert finalizer.success_calls == []
    assert finalizer.failure_calls == []


def test_handle_fal_webhook_marks_failure_for_failed_event() -> None:
    item_id = uuid4()
    job = _job(collection_item_id=item_id)
    repository = FakeGenerationJobRepository(job=job)
    provider = FakeGenerationProvider()
    provider.webhook_event = type(
        'WebhookEvent',
        (),
        {
            'provider_request_id': job.provider_request_id,
            'status': 'FAILED',
            'output_url': None,
            'raw_response': {'status': 'FAILED'},
            'error_message': 'bad prompt',
        },
    )()
    finalizer = FakeGenerationFinalizer()

    use_case = HandleFalWebhookUseCase(repository, provider, finalizer)

    assert use_case.execute({'event': 'failed'}) is True
    assert len(finalizer.failure_calls) == 1
    assert finalizer.failure_calls[0]['error_message'] == 'bad prompt'


def test_handle_fal_webhook_fetches_result_when_success_has_no_output_url() -> None:
    item_id = uuid4()
    job = _job(collection_item_id=item_id)
    repository = FakeGenerationJobRepository(job=job)
    provider = FakeGenerationProvider()
    provider.webhook_event = type(
        'WebhookEvent',
        (),
        {
            'provider_request_id': job.provider_request_id,
            'status': 'SUCCEEDED',
            'output_url': None,
            'raw_response': {'status': 'COMPLETED'},
            'error_message': None,
        },
    )()
    provider.result_value = ProviderResult(
        status='SUCCEEDED',
        output_url='https://cdn.example.com/output.png',
        raw_response={'images': [{'url': 'https://cdn.example.com/output.png'}]},
    )
    finalizer = FakeGenerationFinalizer()

    use_case = HandleFalWebhookUseCase(repository, provider, finalizer)

    assert use_case.execute({'event': 'success'}) is True
    assert len(finalizer.success_calls) == 1
    assert finalizer.success_calls[0]['output_url'] == 'https://cdn.example.com/output.png'


def test_handle_fal_webhook_raises_when_collection_item_missing() -> None:
    job = _job(collection_item_id=None)
    repository = FakeGenerationJobRepository(job=job)
    provider = FakeGenerationProvider()
    provider.webhook_event = type(
        'WebhookEvent',
        (),
        {
            'provider_request_id': job.provider_request_id,
            'status': 'FAILED',
            'output_url': None,
            'raw_response': {'status': 'FAILED'},
            'error_message': 'x',
        },
    )()
    finalizer = FakeGenerationFinalizer()

    use_case = HandleFalWebhookUseCase(repository, provider, finalizer)

    with pytest.raises(GenerationFinalizationError):
        use_case.execute({'event': 'failed'})


def test_reconcile_generation_job_marks_in_progress() -> None:
    job = _job(collection_item_id=uuid4())
    repository = FakeGenerationJobRepository(job=job)
    provider = FakeGenerationProvider()
    provider.status_value = ProviderStatus(status='IN_PROGRESS')
    finalizer = FakeGenerationFinalizer()

    use_case = ReconcileGenerationJobUseCase(repository, provider, finalizer)

    result = use_case.execute(job)

    assert repository.marked_in_progress_job_id == job.id
    assert result == job


def test_reconcile_generation_job_finalizes_failure_when_provider_failed() -> None:
    item_id = uuid4()
    job = _job(collection_item_id=item_id)
    repository = FakeGenerationJobRepository(job=job)
    provider = FakeGenerationProvider()
    provider.status_value = ProviderStatus(status='FAILED')
    finalizer = FakeGenerationFinalizer()

    use_case = ReconcileGenerationJobUseCase(repository, provider, finalizer)

    result = use_case.execute(job)

    assert result == job
    assert len(finalizer.failure_calls) == 1
    assert finalizer.failure_calls[0]['item_id'] == item_id


def test_reconcile_generation_job_finalizes_success_when_result_has_output() -> None:
    item_id = uuid4()
    job = _job(collection_item_id=item_id)
    repository = FakeGenerationJobRepository(job=job)
    provider = FakeGenerationProvider()
    provider.status_value = ProviderStatus(status='SUCCEEDED')
    provider.result_value = ProviderResult(
        status='SUCCEEDED',
        output_url='https://cdn.example.com/generated.jpg',
        raw_response={'status': 'COMPLETED'},
    )
    finalizer = FakeGenerationFinalizer()

    use_case = ReconcileGenerationJobUseCase(repository, provider, finalizer)

    result = use_case.execute(job)

    assert result == job
    assert len(finalizer.success_calls) == 1
    assert finalizer.success_calls[0]['output_url'] == 'https://cdn.example.com/generated.jpg'


def test_reconcile_generation_job_finalizes_failure_when_result_missing_output() -> None:
    item_id = uuid4()
    job = _job(collection_item_id=item_id)
    repository = FakeGenerationJobRepository(job=job)
    provider = FakeGenerationProvider()
    provider.status_value = ProviderStatus(status='SUCCEEDED')
    provider.result_value = ProviderResult(
        status='FAILED',
        output_url=None,
        raw_response={'status': 'FAILED'},
        error_message='provider rejected request',
    )
    finalizer = FakeGenerationFinalizer()

    use_case = ReconcileGenerationJobUseCase(repository, provider, finalizer)

    result = use_case.execute(job)

    assert result == job
    assert len(finalizer.failure_calls) == 1
    assert finalizer.failure_calls[0]['error_message'] == 'provider rejected request'
