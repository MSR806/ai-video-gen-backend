from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ai_video_gen_backend.application.generation.handle_fal_webhook import (
    HandleFalWebhookUseCase,
)
from ai_video_gen_backend.domain.generation import (
    GeneratedOutput,
    GenerationRun,
    GenerationRunOutput,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
)


def _copy_run(run: GenerationRun, **changes: object) -> GenerationRun:
    return GenerationRun(
        id=changes.get('id', run.id),  # type: ignore[arg-type]
        project_id=changes.get('project_id', run.project_id),  # type: ignore[arg-type]
        operation_key=changes.get('operation_key', run.operation_key),  # type: ignore[arg-type]
        provider=changes.get('provider', run.provider),  # type: ignore[arg-type]
        model_key=changes.get('model_key', run.model_key),  # type: ignore[arg-type]
        endpoint_id=changes.get('endpoint_id', run.endpoint_id),  # type: ignore[arg-type]
        status=changes.get('status', run.status),  # type: ignore[arg-type]
        requested_output_count=changes.get('requested_output_count', run.requested_output_count),  # type: ignore[arg-type]
        inputs_json=changes.get('inputs_json', run.inputs_json),  # type: ignore[arg-type]
        provider_request_id=changes.get('provider_request_id', run.provider_request_id),  # type: ignore[arg-type]
        provider_response_json=changes.get('provider_response_json', run.provider_response_json),  # type: ignore[arg-type]
        idempotency_key=changes.get('idempotency_key', run.idempotency_key),  # type: ignore[arg-type]
        error_code=changes.get('error_code', run.error_code),  # type: ignore[arg-type]
        error_message=changes.get('error_message', run.error_message),  # type: ignore[arg-type]
        submitted_at=changes.get('submitted_at', run.submitted_at),  # type: ignore[arg-type]
        completed_at=changes.get('completed_at', run.completed_at),  # type: ignore[arg-type]
        created_at=changes.get('created_at', run.created_at),  # type: ignore[arg-type]
        updated_at=changes.get('updated_at', run.updated_at),  # type: ignore[arg-type]
    )


def _copy_output(output: GenerationRunOutput, **changes: object) -> GenerationRunOutput:
    return GenerationRunOutput(
        id=changes.get('id', output.id),  # type: ignore[arg-type]
        run_id=changes.get('run_id', output.run_id),  # type: ignore[arg-type]
        output_index=changes.get('output_index', output.output_index),  # type: ignore[arg-type]
        status=changes.get('status', output.status),  # type: ignore[arg-type]
        provider_output_json=changes.get('provider_output_json', output.provider_output_json),  # type: ignore[arg-type]
        stored_output_json=changes.get('stored_output_json', output.stored_output_json),  # type: ignore[arg-type]
        error_code=changes.get('error_code', output.error_code),  # type: ignore[arg-type]
        error_message=changes.get('error_message', output.error_message),  # type: ignore[arg-type]
        created_at=changes.get('created_at', output.created_at),  # type: ignore[arg-type]
        updated_at=changes.get('updated_at', output.updated_at),  # type: ignore[arg-type]
    )


class FakeGenerationRunRepository:
    def __init__(self, run: GenerationRun, outputs: list[GenerationRunOutput]) -> None:
        self.run = run
        self.outputs = outputs

    def create_run(self, **kwargs: object) -> GenerationRun:
        del kwargs
        raise NotImplementedError

    def create_run_outputs(self, *, run_id: UUID, output_count: int) -> list[GenerationRunOutput]:
        del run_id, output_count
        raise NotImplementedError

    def get_run_by_id(self, run_id: UUID) -> GenerationRun | None:
        return self.run if self.run.id == run_id else None

    def get_run_by_provider_request_id(self, provider_request_id: str) -> GenerationRun | None:
        return self.run if self.run.provider_request_id == provider_request_id else None

    def get_run_by_idempotency_key(
        self, *, project_id: UUID, idempotency_key: str
    ) -> GenerationRun | None:
        del project_id, idempotency_key
        return None

    def list_outputs_by_run_id(self, run_id: UUID) -> list[GenerationRunOutput]:
        assert run_id == self.run.id
        return list(self.outputs)

    def mark_run_submitted(self, run_id: UUID, *, provider_request_id: str) -> GenerationRun:
        del run_id, provider_request_id
        raise NotImplementedError

    def mark_run_in_progress(self, run_id: UUID) -> GenerationRun:
        del run_id
        raise NotImplementedError

    def mark_run_succeeded(
        self, run_id: UUID, *, provider_response_json: dict[str, object]
    ) -> GenerationRun:
        assert run_id == self.run.id
        self.run = _copy_run(
            self.run,
            status='SUCCEEDED',
            provider_response_json=provider_response_json,
            completed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            error_code=None,
            error_message=None,
        )
        return self.run

    def mark_run_partial_failed(
        self, run_id: UUID, *, provider_response_json: dict[str, object], error_message: str
    ) -> GenerationRun:
        assert run_id == self.run.id
        self.run = _copy_run(
            self.run,
            status='PARTIAL_FAILED',
            provider_response_json=provider_response_json,
            error_code='partial_failed',
            error_message=error_message,
            completed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        return self.run

    def mark_run_failed(
        self,
        run_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun:
        assert run_id == self.run.id
        self.run = _copy_run(
            self.run,
            status='FAILED',
            error_code=error_code,
            error_message=error_message,
            provider_response_json=provider_response_json,
            completed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        return self.run

    def mark_run_cancelled(
        self,
        run_id: UUID,
        *,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun:
        del run_id, error_message, provider_response_json
        raise NotImplementedError

    def mark_output_ready(
        self,
        *,
        output_id: UUID,
        provider_output_json: dict[str, object],
        stored_output_json: dict[str, object],
    ) -> GenerationRunOutput:
        for idx, output in enumerate(self.outputs):
            if output.id == output_id:
                next_output = _copy_output(
                    output,
                    status='READY',
                    provider_output_json=provider_output_json,
                    stored_output_json=stored_output_json,
                    error_code=None,
                    error_message=None,
                    updated_at=datetime.now(UTC),
                )
                self.outputs[idx] = next_output
                return next_output
        raise LookupError(output_id)

    def mark_output_failed(
        self,
        *,
        output_id: UUID,
        error_code: str,
        error_message: str,
        provider_output_json: dict[str, object] | None = None,
    ) -> GenerationRunOutput:
        for idx, output in enumerate(self.outputs):
            if output.id == output_id:
                next_output = _copy_output(
                    output,
                    status='FAILED',
                    error_code=error_code,
                    error_message=error_message,
                    provider_output_json=provider_output_json,
                    updated_at=datetime.now(UTC),
                )
                self.outputs[idx] = next_output
                return next_output
        raise LookupError(output_id)


class FakeProvider:
    def __init__(
        self,
        *,
        webhook_event: ProviderWebhookEvent | None,
        result: ProviderResult | None = None,
    ) -> None:
        self.webhook_event = webhook_event
        self.result_payload = result

    def submit(
        self,
        *,
        endpoint_id: str,
        inputs: dict[str, object],
        webhook_url: str,
    ) -> ProviderSubmission:
        del endpoint_id, inputs, webhook_url
        return ProviderSubmission(provider_request_id='req')

    def status(self, *, endpoint_id: str, provider_request_id: str) -> ProviderStatus:
        del endpoint_id, provider_request_id
        return ProviderStatus(status='IN_PROGRESS')

    def result(self, *, endpoint_id: str, provider_request_id: str) -> ProviderResult:
        del endpoint_id, provider_request_id
        if self.result_payload is None:
            return ProviderResult(
                status='FAILED',
                outputs=[],
                raw_response={},
                error_message='failed',
            )
        return self.result_payload

    def cancel(self, *, endpoint_id: str, provider_request_id: str) -> None:
        del endpoint_id, provider_request_id

    def parse_webhook(self, payload: dict[str, object]) -> ProviderWebhookEvent | None:
        del payload
        return self.webhook_event


class FakeFinalizer:
    def __init__(self, repository: FakeGenerationRunRepository) -> None:
        self.repository = repository

    def finalize_output_success(self, *, output_id: UUID, output: dict[str, object]) -> None:
        self.repository.mark_output_ready(
            output_id=output_id,
            provider_output_json=output,
            stored_output_json={'storedUrl': 'https://cdn.test/item.png'},
        )

    def finalize_output_failure(
        self,
        *,
        output_id: UUID,
        error_code: str,
        error_message: str,
        provider_output_json: dict[str, object] | None = None,
    ) -> None:
        self.repository.mark_output_failed(
            output_id=output_id,
            error_code=error_code,
            error_message=error_message,
            provider_output_json=provider_output_json,
        )


def _run_fixture() -> GenerationRun:
    now = datetime.now(UTC)
    return GenerationRun(
        id=uuid4(),
        project_id=uuid4(),
        operation_key='text_to_image',
        provider='fal',
        model_key='nano_banana',
        endpoint_id='fal-ai/nano-banana',
        status='IN_PROGRESS',
        requested_output_count=2,
        inputs_json={'prompt': 'cat'},
        provider_request_id='provider-req-1',
        provider_response_json=None,
        idempotency_key=None,
        error_code=None,
        error_message=None,
        submitted_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


def _output_fixture(run_id: UUID, index: int) -> GenerationRunOutput:
    now = datetime.now(UTC)
    return GenerationRunOutput(
        id=uuid4(),
        run_id=run_id,
        output_index=index,
        status='QUEUED',
        provider_output_json=None,
        stored_output_json=None,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def test_handle_fal_webhook_succeeds_with_partial_outputs() -> None:
    run = _run_fixture()
    outputs = [_output_fixture(run.id, 0), _output_fixture(run.id, 1)]
    repository = FakeGenerationRunRepository(run, outputs)
    provider = FakeProvider(
        webhook_event=ProviderWebhookEvent(
            provider_request_id='provider-req-1',
            status='SUCCEEDED',
            outputs=[
                GeneratedOutput(
                    index=0,
                    media_type='image',
                    provider_url='https://provider.test/0.png',
                    metadata={},
                )
            ],
            raw_response={'images': [{'url': 'https://provider.test/0.png'}]},
        )
    )
    finalizer = FakeFinalizer(repository)
    use_case = HandleFalWebhookUseCase(
        generation_run_repository=repository,
        generation_provider=provider,
        generation_finalizer=finalizer,  # type: ignore[arg-type]
    )

    handled = use_case.execute({'request_id': 'provider-req-1'})

    assert handled is True
    assert repository.run.status == 'PARTIAL_FAILED'
    assert [output.status for output in repository.outputs] == ['READY', 'FAILED']


def test_handle_fal_webhook_marks_run_failed() -> None:
    run = _run_fixture()
    outputs = [_output_fixture(run.id, 0), _output_fixture(run.id, 1)]
    repository = FakeGenerationRunRepository(run, outputs)
    provider = FakeProvider(
        webhook_event=ProviderWebhookEvent(
            provider_request_id='provider-req-1',
            status='FAILED',
            outputs=[],
            raw_response={'error': 'failed'},
            error_message='provider failed',
        )
    )
    finalizer = FakeFinalizer(repository)
    use_case = HandleFalWebhookUseCase(
        generation_run_repository=repository,
        generation_provider=provider,
        generation_finalizer=finalizer,  # type: ignore[arg-type]
    )

    handled = use_case.execute({'request_id': 'provider-req-1'})

    assert handled is True
    assert repository.run.status == 'FAILED'
    assert [output.status for output in repository.outputs] == ['FAILED', 'FAILED']


def test_handle_fal_webhook_returns_false_on_unparseable_payload() -> None:
    run = _run_fixture()
    outputs = [_output_fixture(run.id, 0)]
    repository = FakeGenerationRunRepository(run, outputs)
    provider = FakeProvider(webhook_event=None)
    finalizer = FakeFinalizer(repository)
    use_case = HandleFalWebhookUseCase(
        generation_run_repository=repository,
        generation_provider=provider,
        generation_finalizer=finalizer,  # type: ignore[arg-type]
    )

    handled = use_case.execute({'unexpected': 'payload'})
    assert handled is False

    broken_provider = FakeProvider(
        webhook_event=ProviderWebhookEvent(
            provider_request_id='provider-req-1',
            status='SUCCEEDED',
            outputs=[],
            raw_response={},
        ),
        result=ProviderResult(
            status='FAILED',
            outputs=[],
            raw_response={},
            error_message='failed',
        ),
    )
    broken_use_case = HandleFalWebhookUseCase(
        generation_run_repository=repository,
        generation_provider=broken_provider,
        generation_finalizer=finalizer,  # type: ignore[arg-type]
    )
    repository.outputs = []

    handled_broken = broken_use_case.execute({'request_id': 'provider-req-1'})

    assert handled_broken is True
    assert repository.run.status == 'FAILED'
