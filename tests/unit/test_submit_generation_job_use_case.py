from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.generation.submit_generation_run import (
    GenerationModelRegistryLoadError,
    InvalidOutputCountError,
    ProviderSubmissionFailedError,
    SubmitGenerationRunUseCase,
    UnsupportedBatchOutputCountError,
)
from ai_video_gen_backend.application.generation.validate_generation_inputs import (
    GenerationInputValidator,
)
from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    CollectionItemCreationPayload,
    JsonValue,
)
from ai_video_gen_backend.domain.generation import (
    CapabilityRegistryError,
    GenerationCapabilities,
    GenerationRun,
    GenerationRunOutput,
    GenerationRunRequest,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
    ResolvedGenerationOperation,
)


class FakeCollectionItemRepository:
    def __init__(self) -> None:
        self.created_payloads: list[CollectionItemCreationPayload] = []

    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]:
        del collection_id
        return []

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None:
        del item_id
        return None

    def get_items_by_run_id(self, run_id: UUID) -> list[CollectionItem]:
        del run_id
        return []

    def get_item_by_generation_run_output_id(
        self, generation_run_output_id: UUID
    ) -> CollectionItem | None:
        del generation_run_output_id
        return None

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem:
        self.created_payloads.append(payload)
        now = datetime.now(UTC)
        return CollectionItem(
            id=uuid4(),
            project_id=payload.project_id,
            collection_id=payload.collection_id,
            media_type=payload.media_type,
            status=payload.status,
            name=payload.name,
            description=payload.description,
            url=payload.url,
            metadata=payload.metadata,
            generation_source=payload.generation_source,
            generation_error_message=payload.generation_error_message,
            created_at=now,
            updated_at=now,
            run_id=payload.run_id,
            generation_run_output_id=payload.generation_run_output_id,
            storage_provider=payload.storage_provider,
            storage_bucket=payload.storage_bucket,
            storage_key=payload.storage_key,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
        )

    def delete_item(self, item_id: UUID) -> bool:
        del item_id
        return False

    def mark_generated_item_ready(
        self,
        *,
        item_id: UUID,
        url: str,
        metadata: dict[str, JsonValue],
        storage_provider: str | None,
        storage_bucket: str | None,
        storage_key: str | None,
        mime_type: str | None,
        size_bytes: int | None,
    ) -> CollectionItem | None:
        del (
            item_id,
            url,
            metadata,
            storage_provider,
            storage_bucket,
            storage_key,
            mime_type,
            size_bytes,
        )
        return None

    def mark_generated_item_failed(
        self, *, item_id: UUID, error_message: str
    ) -> CollectionItem | None:
        del item_id, error_message
        return None


class FakeGenerationRunRepository:
    def __init__(self, *, existing: GenerationRun | None = None) -> None:
        self.existing = existing
        self.created_run: GenerationRun | None = None
        self.created_outputs: list[GenerationRunOutput] = []
        self.failed_run_errors: list[tuple[str, str]] = []
        self.failed_output_errors: list[tuple[UUID, str, str]] = []

    def create_run(
        self,
        *,
        project_id: UUID,
        operation_key: str,
        provider: str,
        model_key: str,
        endpoint_id: str,
        requested_output_count: int,
        inputs_json: dict[str, object],
        idempotency_key: str | None,
    ) -> GenerationRun:
        now = datetime.now(UTC)
        run = GenerationRun(
            id=uuid4(),
            project_id=project_id,
            operation_key=operation_key,
            provider=provider,
            model_key=model_key,
            endpoint_id=endpoint_id,
            status='QUEUED',
            requested_output_count=requested_output_count,
            inputs_json=inputs_json,
            provider_request_id=None,
            provider_response_json=None,
            idempotency_key=idempotency_key,
            error_code=None,
            error_message=None,
            submitted_at=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        self.created_run = run
        return run

    def create_run_outputs(self, *, run_id: UUID, output_count: int) -> list[GenerationRunOutput]:
        now = datetime.now(UTC)
        outputs = [
            GenerationRunOutput(
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
            for index in range(output_count)
        ]
        self.created_outputs = outputs
        return outputs

    def get_run_by_id(self, run_id: UUID) -> GenerationRun | None:
        if self.created_run is not None and self.created_run.id == run_id:
            return self.created_run
        return None

    def get_run_by_provider_request_id(self, provider_request_id: str) -> GenerationRun | None:
        del provider_request_id
        return None

    def get_run_by_idempotency_key(
        self,
        *,
        project_id: UUID,
        idempotency_key: str,
    ) -> GenerationRun | None:
        del project_id, idempotency_key
        return self.existing

    def list_outputs_by_run_id(self, run_id: UUID) -> list[GenerationRunOutput]:
        del run_id
        return self.created_outputs

    def mark_run_submitted(self, run_id: UUID, *, provider_request_id: str) -> GenerationRun:
        assert self.created_run is not None
        assert self.created_run.id == run_id
        now = datetime.now(UTC)
        return GenerationRun(
            id=self.created_run.id,
            project_id=self.created_run.project_id,
            operation_key=self.created_run.operation_key,
            provider=self.created_run.provider,
            model_key=self.created_run.model_key,
            endpoint_id=self.created_run.endpoint_id,
            status='IN_PROGRESS',
            requested_output_count=self.created_run.requested_output_count,
            inputs_json=self.created_run.inputs_json,
            provider_request_id=provider_request_id,
            provider_response_json=None,
            idempotency_key=self.created_run.idempotency_key,
            error_code=None,
            error_message=None,
            submitted_at=now,
            completed_at=None,
            created_at=self.created_run.created_at,
            updated_at=now,
        )

    def mark_run_in_progress(self, run_id: UUID) -> GenerationRun:
        del run_id
        raise NotImplementedError

    def mark_run_succeeded(
        self, run_id: UUID, *, provider_response_json: dict[str, object]
    ) -> GenerationRun:
        del run_id, provider_response_json
        raise NotImplementedError

    def mark_run_partial_failed(
        self, run_id: UUID, *, provider_response_json: dict[str, object], error_message: str
    ) -> GenerationRun:
        del run_id, provider_response_json, error_message
        raise NotImplementedError

    def mark_run_failed(
        self,
        run_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun:
        assert self.created_run is not None
        self.failed_run_errors.append((error_code, error_message))
        now = datetime.now(UTC)
        return GenerationRun(
            id=run_id,
            project_id=self.created_run.project_id,
            operation_key=self.created_run.operation_key,
            provider=self.created_run.provider,
            model_key=self.created_run.model_key,
            endpoint_id=self.created_run.endpoint_id,
            status='FAILED',
            requested_output_count=self.created_run.requested_output_count,
            inputs_json=self.created_run.inputs_json,
            provider_request_id=self.created_run.provider_request_id,
            provider_response_json=provider_response_json,
            idempotency_key=self.created_run.idempotency_key,
            error_code=error_code,
            error_message=error_message,
            submitted_at=self.created_run.submitted_at,
            completed_at=now,
            created_at=self.created_run.created_at,
            updated_at=now,
        )

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
        del output_id, provider_output_json, stored_output_json
        raise NotImplementedError

    def mark_output_failed(
        self,
        *,
        output_id: UUID,
        error_code: str,
        error_message: str,
        provider_output_json: dict[str, object] | None = None,
    ) -> GenerationRunOutput:
        del provider_output_json
        self.failed_output_errors.append((output_id, error_code, error_message))
        for output in self.created_outputs:
            if output.id == output_id:
                return GenerationRunOutput(
                    id=output.id,
                    run_id=output.run_id,
                    output_index=output.output_index,
                    status='FAILED',
                    provider_output_json=None,
                    stored_output_json=None,
                    error_code=error_code,
                    error_message=error_message,
                    created_at=output.created_at,
                    updated_at=output.updated_at,
                )
        raise LookupError(output_id)


class FakeProvider:
    def __init__(self) -> None:
        self.submit_calls: list[dict[str, object]] = []

    def submit(
        self,
        *,
        endpoint_id: str,
        inputs: dict[str, object],
        webhook_url: str,
    ) -> ProviderSubmission:
        self.submit_calls.append(
            {
                'endpoint_id': endpoint_id,
                'inputs': inputs,
                'webhook_url': webhook_url,
            }
        )
        return ProviderSubmission(provider_request_id='provider-req-1')

    def status(self, *, endpoint_id: str, provider_request_id: str) -> ProviderStatus:
        del endpoint_id, provider_request_id
        return ProviderStatus(status='IN_PROGRESS')

    def result(self, *, endpoint_id: str, provider_request_id: str) -> ProviderResult:
        del endpoint_id, provider_request_id
        return ProviderResult(
            status='FAILED',
            outputs=[],
            raw_response={},
            error_message='unsupported',
        )

    def cancel(self, *, endpoint_id: str, provider_request_id: str) -> None:
        del endpoint_id, provider_request_id

    def parse_webhook(self, payload: dict[str, object]) -> ProviderWebhookEvent | None:
        del payload
        return None


class FailingProvider(FakeProvider):
    def submit(
        self,
        *,
        endpoint_id: str,
        inputs: dict[str, object],
        webhook_url: str,
    ) -> ProviderSubmission:
        del endpoint_id, inputs, webhook_url
        raise RuntimeError('provider request failed')


class FakeCapabilityRegistry:
    def __init__(self, *, supports_batch: bool) -> None:
        self.supports_batch = supports_batch

    def list_capabilities(self) -> GenerationCapabilities:
        return GenerationCapabilities(image=[], video=[])

    def has_model(self, *, model_key: str) -> bool:
        return model_key == 'nano_banana'

    def resolve_operation(
        self, *, model_key: str, operation_key: str
    ) -> ResolvedGenerationOperation | None:
        if model_key != 'nano_banana' or operation_key != 'text_to_image':
            return None

        properties: dict[str, object] = {'prompt': {'type': 'string'}}
        if self.supports_batch:
            properties['num_images'] = {'type': 'integer', 'default': 1}

        return ResolvedGenerationOperation(
            model_key='nano_banana',
            model_display_name='Nano Banana',
            provider='fal',
            media_type='image',
            operation_key='text_to_image',
            operation_type='text_to_image',
            operation_name='Text to Image',
            endpoint_id='fal-ai/nano-banana',
            input_schema={
                'type': 'object',
                'required': ['prompt'],
                'properties': properties,
                'additionalProperties': False,
            },
        )


class FailingCapabilityRegistry:
    def list_capabilities(self) -> GenerationCapabilities:
        raise CapabilityRegistryError('registry unavailable')

    def has_model(self, *, model_key: str) -> bool:
        del model_key
        raise CapabilityRegistryError('registry unavailable')

    def resolve_operation(
        self, *, model_key: str, operation_key: str
    ) -> ResolvedGenerationOperation | None:
        del model_key, operation_key
        raise CapabilityRegistryError('registry unavailable')


def _build_use_case(
    *,
    supports_batch: bool,
) -> tuple[
    SubmitGenerationRunUseCase,
    FakeProvider,
    FakeCollectionItemRepository,
    FakeGenerationRunRepository,
]:
    collection_repo = FakeCollectionItemRepository()
    run_repo = FakeGenerationRunRepository()
    provider = FakeProvider()
    use_case = SubmitGenerationRunUseCase(
        collection_item_repository=collection_repo,
        generation_run_repository=run_repo,
        generation_provider=provider,
        capability_registry=FakeCapabilityRegistry(supports_batch=supports_batch),
        input_validator=GenerationInputValidator(),
        webhook_url='https://webhook.test/fal',
    )
    return use_case, provider, collection_repo, run_repo


def test_submit_generation_run_creates_outputs_and_placeholders() -> None:
    use_case, provider, collection_repo, run_repo = _build_use_case(supports_batch=True)
    request = GenerationRunRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        model_key='nano_banana',
        operation_key='text_to_image',
        inputs={'prompt': 'a cinematic portrait'},
        output_count=2,
        idempotency_key='idem-1',
    )

    submission = use_case.execute(request)

    assert submission.run.status == 'IN_PROGRESS'
    assert len(submission.outputs) == 2
    assert len(collection_repo.created_payloads) == 2
    assert run_repo.created_run is not None
    assert run_repo.created_run.requested_output_count == 2
    assert len(provider.submit_calls) == 1
    assert provider.submit_calls[0]['inputs'] == {
        'prompt': 'a cinematic portrait',
        'num_images': 2,
    }


def test_submit_generation_run_rejects_output_count_outside_bounds() -> None:
    use_case, _, _, _ = _build_use_case(supports_batch=True)
    request = GenerationRunRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        model_key='nano_banana',
        operation_key='text_to_image',
        inputs={'prompt': 'a cinematic portrait'},
        output_count=0,
    )

    with pytest.raises(InvalidOutputCountError):
        use_case.execute(request)


def test_submit_generation_run_rejects_non_batch_operation_when_multiple_outputs() -> None:
    use_case, _, _, _ = _build_use_case(supports_batch=False)
    request = GenerationRunRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        model_key='nano_banana',
        operation_key='text_to_image',
        inputs={'prompt': 'a cinematic portrait'},
        output_count=2,
    )

    with pytest.raises(UnsupportedBatchOutputCountError):
        use_case.execute(request)


def test_submit_generation_run_wraps_capability_registry_failures() -> None:
    collection_repo = FakeCollectionItemRepository()
    run_repo = FakeGenerationRunRepository()
    provider = FakeProvider()
    use_case = SubmitGenerationRunUseCase(
        collection_item_repository=collection_repo,
        generation_run_repository=run_repo,
        generation_provider=provider,
        capability_registry=FailingCapabilityRegistry(),
        input_validator=GenerationInputValidator(),
        webhook_url='https://webhook.test/fal',
    )
    request = GenerationRunRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        model_key='nano_banana',
        operation_key='text_to_image',
        inputs={'prompt': 'a cinematic portrait'},
        output_count=1,
    )

    with pytest.raises(GenerationModelRegistryLoadError):
        use_case.execute(request)


def test_submit_generation_run_marks_failures_when_provider_submit_fails() -> None:
    collection_repo = FakeCollectionItemRepository()
    run_repo = FakeGenerationRunRepository()
    use_case = SubmitGenerationRunUseCase(
        collection_item_repository=collection_repo,
        generation_run_repository=run_repo,
        generation_provider=FailingProvider(),
        capability_registry=FakeCapabilityRegistry(supports_batch=True),
        input_validator=GenerationInputValidator(),
        webhook_url='https://webhook.test/fal',
    )
    request = GenerationRunRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        model_key='nano_banana',
        operation_key='text_to_image',
        inputs={'prompt': 'a cinematic portrait'},
        output_count=2,
    )

    with pytest.raises(ProviderSubmissionFailedError, match='Failed to submit generation request'):
        use_case.execute(request)

    assert run_repo.failed_run_errors
    assert run_repo.failed_run_errors[-1][0] == 'provider_submit_failed'
    assert len(run_repo.failed_output_errors) == 2
    assert all(
        error_code == 'provider_submit_failed' for _, error_code, _ in run_repo.failed_output_errors
    )
