from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.generation.finalize_generation import (
    GenerationFinalizationError,
    GenerationFinalizer,
)
from ai_video_gen_backend.application.generation.handle_fal_webhook import (
    HandleFalWebhookUseCase,
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
    def __init__(self, *, job: GenerationJob | None = None) -> None:
        self.job = job
        self.request_ids: list[str] = []

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
        del job_id
        return self.job

    def get_by_provider_request_id(self, provider_request_id: str) -> GenerationJob | None:
        self.request_ids.append(provider_request_id)
        return self.job

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
        del job_id
        raise NotImplementedError

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
    def __init__(
        self,
        *,
        event: ProviderWebhookEvent | None,
        result: ProviderResult | None = None,
    ) -> None:
        self.event = event
        self.result_value = result
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
        del endpoint_id, provider_request_id
        raise NotImplementedError

    def result(
        self,
        *,
        endpoint_id: str,
        provider_request_id: str,
    ) -> ProviderResult:
        self.result_calls.append((endpoint_id, provider_request_id))
        if self.result_value is None:
            raise RuntimeError('result not configured')
        return self.result_value

    def cancel(self, *, endpoint_id: str, provider_request_id: str) -> None:
        del endpoint_id, provider_request_id

    def parse_webhook(self, payload: dict[str, object]) -> ProviderWebhookEvent | None:
        del payload
        return self.event


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
    with_item: bool = True,
    with_provider_info: bool = True,
) -> GenerationJob:
    now = datetime.now(UTC)
    return GenerationJob(
        id=uuid4(),
        project_id=uuid4(),
        collection_id=uuid4(),
        collection_item_id=uuid4() if with_item else None,
        operation_key='text_to_image',
        provider='fal',
        model_key='nano_banana',
        endpoint_id='fal-ai/nano-banana' if with_provider_info else None,
        status=status,
        inputs_json={'prompt': 'cat'},
        outputs_json=[],
        provider_request_id='req-123' if with_provider_info else None,
        provider_response_json=None,
        idempotency_key=None,
        error_code=None,
        error_message=None,
        submitted_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


def _output(provider_url: str) -> GeneratedOutput:
    return GeneratedOutput(index=0, media_type='image', provider_url=provider_url, metadata={})


def _build_use_case(
    repository: FakeGenerationJobRepository,
    provider: FakeGenerationProvider,
    finalizer: FakeGenerationFinalizer,
) -> HandleFalWebhookUseCase:
    return HandleFalWebhookUseCase(repository, provider, cast(GenerationFinalizer, finalizer))


def test_execute_returns_false_when_payload_is_not_a_webhook_event() -> None:
    provider = FakeGenerationProvider(event=None)
    repository = FakeGenerationJobRepository(job=_job_fixture())
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    handled = use_case.execute({'status': 'unknown'})

    assert handled is False
    assert repository.request_ids == []
    assert finalizer.success_calls == []
    assert finalizer.failure_calls == []


def test_execute_returns_false_when_no_job_matches_request_id() -> None:
    event = ProviderWebhookEvent(
        provider_request_id='req-404',
        status='SUCCEEDED',
        outputs=[_output('https://provider.test/image.png')],
        raw_response={'status': 'OK'},
    )
    provider = FakeGenerationProvider(event=event)
    repository = FakeGenerationJobRepository(job=None)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    handled = use_case.execute({'request_id': 'req-404'})

    assert handled is False
    assert repository.request_ids == ['req-404']
    assert finalizer.success_calls == []


@pytest.mark.parametrize('terminal_status', ['SUCCEEDED', 'FAILED', 'CANCELLED'])
def test_execute_short_circuits_terminal_jobs(
    terminal_status: Literal['SUCCEEDED', 'FAILED', 'CANCELLED'],
) -> None:
    event = ProviderWebhookEvent(
        provider_request_id='req-123',
        status='FAILED',
        outputs=[],
        raw_response={'status': 'FAILED'},
    )
    provider = FakeGenerationProvider(event=event)
    repository = FakeGenerationJobRepository(job=_job_fixture(status=terminal_status))
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    handled = use_case.execute({'request_id': 'req-123'})

    assert handled is True
    assert finalizer.success_calls == []
    assert finalizer.failure_calls == []


def test_execute_raises_when_job_has_no_collection_item() -> None:
    event = ProviderWebhookEvent(
        provider_request_id='req-123',
        status='FAILED',
        outputs=[],
        raw_response={'status': 'FAILED'},
    )
    provider = FakeGenerationProvider(event=event)
    repository = FakeGenerationJobRepository(job=_job_fixture(with_item=False))
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    with pytest.raises(GenerationFinalizationError, match='no linked collection item'):
        use_case.execute({'request_id': 'req-123'})


def test_execute_finalizes_success_when_event_contains_outputs() -> None:
    event = ProviderWebhookEvent(
        provider_request_id='req-123',
        status='SUCCEEDED',
        outputs=[_output('https://provider.test/image.png')],
        raw_response={'status': 'OK'},
    )
    provider = FakeGenerationProvider(event=event)
    job = _job_fixture()
    repository = FakeGenerationJobRepository(job=job)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    handled = use_case.execute({'request_id': 'req-123'})

    assert handled is True
    assert len(finalizer.success_calls) == 1
    assert finalizer.success_calls[0]['job_id'] == job.id
    output = finalizer.success_calls[0]['output']
    assert isinstance(output, dict)
    assert output['provider_url'] == 'https://provider.test/image.png'
    assert finalizer.failure_calls == []


def test_execute_fetches_result_when_success_event_has_no_outputs_and_then_finalizes_success() -> (
    None
):
    event = ProviderWebhookEvent(
        provider_request_id='req-123',
        status='SUCCEEDED',
        outputs=[],
        raw_response={'status': 'OK'},
    )
    result = ProviderResult(
        status='SUCCEEDED',
        outputs=[_output('https://provider.test/fetched.png')],
        raw_response={'images': [{'url': 'https://provider.test/fetched.png'}]},
    )
    provider = FakeGenerationProvider(event=event, result=result)
    job = _job_fixture()
    repository = FakeGenerationJobRepository(job=job)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    handled = use_case.execute({'request_id': 'req-123'})

    assert handled is True
    assert provider.result_calls == [('fal-ai/nano-banana', 'req-123')]
    assert len(finalizer.success_calls) == 1
    assert finalizer.success_calls[0]['provider_response_json'] == result.raw_response


def test_execute_marks_failure_when_result_fetch_after_success_event_returns_failed() -> None:
    event = ProviderWebhookEvent(
        provider_request_id='req-123',
        status='SUCCEEDED',
        outputs=[],
        raw_response={'status': 'OK'},
    )
    result = ProviderResult(
        status='FAILED',
        outputs=[],
        raw_response={'status': 'FAILED'},
        error_message='provider said no',
    )
    provider = FakeGenerationProvider(event=event, result=result)
    job = _job_fixture()
    repository = FakeGenerationJobRepository(job=job)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    handled = use_case.execute({'request_id': 'req-123'})

    assert handled is True
    assert len(finalizer.failure_calls) == 1
    assert finalizer.failure_calls[0]['error_message'] == 'provider said no'


def test_execute_marks_failure_when_success_no_outputs_and_no_result_lookup() -> None:
    event = ProviderWebhookEvent(
        provider_request_id='req-123',
        status='SUCCEEDED',
        outputs=[],
        raw_response={'status': 'OK'},
    )
    provider = FakeGenerationProvider(event=event)
    job = _job_fixture(with_provider_info=False)
    repository = FakeGenerationJobRepository(job=job)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    handled = use_case.execute({'request_id': 'req-123'})

    assert handled is True
    assert provider.result_calls == []
    assert len(finalizer.failure_calls) == 1
    assert (
        finalizer.failure_calls[0]['error_message']
        == 'Provider reported success without output URL'
    )


def test_execute_marks_failure_for_failed_event_with_provider_error_message() -> None:
    event = ProviderWebhookEvent(
        provider_request_id='req-123',
        status='FAILED',
        outputs=[],
        raw_response={'status': 'FAILED'},
        error_message='quota exceeded',
    )
    provider = FakeGenerationProvider(event=event)
    job = _job_fixture()
    repository = FakeGenerationJobRepository(job=job)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    handled = use_case.execute({'request_id': 'req-123'})

    assert handled is True
    assert len(finalizer.failure_calls) == 1
    assert finalizer.failure_calls[0]['error_message'] == 'quota exceeded'


def test_execute_marks_failure_for_failed_event_with_default_message() -> None:
    event = ProviderWebhookEvent(
        provider_request_id='req-123',
        status='FAILED',
        outputs=[],
        raw_response={'status': 'FAILED'},
        error_message=None,
    )
    provider = FakeGenerationProvider(event=event)
    job = _job_fixture()
    repository = FakeGenerationJobRepository(job=job)
    finalizer = FakeGenerationFinalizer()
    use_case = _build_use_case(repository, provider, finalizer)

    handled = use_case.execute({'request_id': 'req-123'})

    assert handled is True
    assert len(finalizer.failure_calls) == 1
    assert finalizer.failure_calls[0]['error_message'] == 'Generation failed'
