from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.generation.submit_generation_job import (
    SubmitGenerationJobUseCase,
    UnsupportedModelKeyError,
    UnsupportedOperationKeyError,
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
    GenerationCapabilities,
    GenerationJob,
    GenerationRequest,
    ModelCapability,
    OperationCapability,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
    ResolvedGenerationOperation,
)
from ai_video_gen_backend.domain.types import JsonObject


class FakeCollectionItemRepository:
    def __init__(self, *, assign_returns_none: bool = False) -> None:
        self.assign_returns_none = assign_returns_none
        self.created_payload: CollectionItemCreationPayload | None = None
        self.assigned: list[tuple[UUID, UUID]] = []
        self.failed_calls: list[tuple[UUID, str]] = []
        self.created_item_id = uuid4()

    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]:
        del collection_id
        return []

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None:
        del item_id
        return None

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem:
        self.created_payload = payload
        now = datetime.now(UTC)
        return CollectionItem(
            id=self.created_item_id,
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
            storage_provider=payload.storage_provider,
            storage_bucket=payload.storage_bucket,
            storage_key=payload.storage_key,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
        )

    def delete_item(self, item_id: UUID) -> bool:
        del item_id
        return False

    def assign_job_id(self, *, item_id: UUID, job_id: UUID) -> CollectionItem | None:
        self.assigned.append((item_id, job_id))
        if self.assign_returns_none:
            return None

        now = datetime.now(UTC)
        return CollectionItem(
            id=item_id,
            project_id=uuid4(),
            collection_id=uuid4(),
            media_type='image',
            status='GENERATING',
            name='Generated',
            description='AI generation in progress',
            url=None,
            metadata={'thumbnailUrl': '', 'width': 0, 'height': 0, 'format': 'png'},
            generation_source='fal',
            generation_error_message=None,
            created_at=now,
            updated_at=now,
            job_id=job_id,
        )

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
        self,
        *,
        item_id: UUID,
        error_message: str,
    ) -> CollectionItem | None:
        self.failed_calls.append((item_id, error_message))
        return None


class FakeGenerationJobRepository:
    def __init__(self, *, existing_by_idempotency: GenerationJob | None = None) -> None:
        self.existing_by_idempotency = existing_by_idempotency
        self.created_jobs: list[GenerationJob] = []
        self.failed_calls: list[dict[str, object]] = []

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
        now = datetime.now(UTC)
        job = GenerationJob(
            id=uuid4(),
            project_id=project_id,
            collection_id=collection_id,
            collection_item_id=collection_item_id,
            operation_key=operation_key,
            provider=provider,
            model_key=model_key,
            endpoint_id=endpoint_id,
            status='QUEUED',
            inputs_json=inputs_json,
            outputs_json=[],
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
        self.created_jobs.append(job)
        return job

    def get_by_id(self, job_id: UUID) -> GenerationJob | None:
        for job in self.created_jobs:
            if job.id == job_id:
                return job
        return None

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
        return self.existing_by_idempotency

    def mark_submitted(self, job_id: UUID, *, provider_request_id: str) -> GenerationJob:
        base = self.get_by_id(job_id)
        assert base is not None
        return GenerationJob(
            id=base.id,
            project_id=base.project_id,
            collection_id=base.collection_id,
            collection_item_id=base.collection_item_id,
            operation_key=base.operation_key,
            provider=base.provider,
            model_key=base.model_key,
            endpoint_id=base.endpoint_id,
            status='IN_PROGRESS',
            inputs_json=base.inputs_json,
            outputs_json=base.outputs_json,
            provider_request_id=provider_request_id,
            provider_response_json=None,
            idempotency_key=base.idempotency_key,
            error_code=None,
            error_message=None,
            submitted_at=datetime.now(UTC),
            completed_at=None,
            created_at=base.created_at,
            updated_at=datetime.now(UTC),
        )

    def mark_in_progress(self, job_id: UUID) -> GenerationJob:
        base = self.get_by_id(job_id)
        assert base is not None
        return base

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
        self.failed_calls.append(
            {
                'job_id': job_id,
                'error_code': error_code,
                'error_message': error_message,
                'provider_response_json': provider_response_json,
            }
        )
        base = self.get_by_id(job_id)
        assert base is not None
        return GenerationJob(
            id=base.id,
            project_id=base.project_id,
            collection_id=base.collection_id,
            collection_item_id=base.collection_item_id,
            operation_key=base.operation_key,
            provider=base.provider,
            model_key=base.model_key,
            endpoint_id=base.endpoint_id,
            status='FAILED',
            inputs_json=base.inputs_json,
            outputs_json=base.outputs_json,
            provider_request_id=base.provider_request_id,
            provider_response_json=provider_response_json,
            idempotency_key=base.idempotency_key,
            error_code=error_code,
            error_message=error_message,
            submitted_at=base.submitted_at,
            completed_at=datetime.now(UTC),
            created_at=base.created_at,
            updated_at=datetime.now(UTC),
        )


class FakeGenerationProvider:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
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
        if self.error is not None:
            raise self.error
        return ProviderSubmission(provider_request_id='req-123')

    def status(self, *, endpoint_id: str, provider_request_id: str) -> ProviderStatus:
        del endpoint_id, provider_request_id
        return ProviderStatus(status='IN_PROGRESS')

    def result(self, *, endpoint_id: str, provider_request_id: str) -> ProviderResult:
        del endpoint_id, provider_request_id
        return ProviderResult(status='FAILED', outputs=[], raw_response={})

    def cancel(self, *, endpoint_id: str, provider_request_id: str) -> None:
        del endpoint_id, provider_request_id

    def parse_webhook(self, payload: dict[str, object]) -> ProviderWebhookEvent | None:
        del payload
        return None


class FakeCapabilityRegistry:
    def __init__(
        self,
        *,
        has_model: bool,
        resolved_operation: ResolvedGenerationOperation | None,
    ) -> None:
        self.has_model_value = has_model
        self.resolved_operation = resolved_operation

    def list_capabilities(self) -> GenerationCapabilities:
        model = ModelCapability(
            model='Nano Banana',
            model_key='nano_banana',
            provider='fal',
            media_type='image',
            operations=[
                OperationCapability(
                    operation_key='text_to_image',
                    endpoint_id='fal-ai/nano-banana',
                    required=['prompt'],
                    input_schema={'type': 'object'},
                    fields=[],
                )
            ],
        )
        return GenerationCapabilities(image=[model], video=[])

    def has_model(self, *, model_key: str) -> bool:
        del model_key
        return self.has_model_value

    def resolve_operation(
        self,
        *,
        model_key: str,
        operation_key: str,
    ) -> ResolvedGenerationOperation | None:
        del model_key, operation_key
        return self.resolved_operation


class FakeInputValidator(GenerationInputValidator):
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, JsonObject]] = []

    def validate(self, *, inputs: JsonObject, schema: JsonObject) -> None:
        self.calls.append({'inputs': inputs, 'schema': schema})
        if self.error is not None:
            raise self.error


def _resolved_operation(
    *, media_type: Literal['image', 'video'] = 'image'
) -> ResolvedGenerationOperation:
    return ResolvedGenerationOperation(
        model_key='nano_banana',
        model_display_name='Nano Banana',
        provider='fal',
        media_type=media_type,
        operation_key='text_to_image',
        endpoint_id='fal-ai/nano-banana',
        input_schema={
            'type': 'object',
            'required': ['prompt'],
            'properties': {'prompt': {'type': 'string'}},
            'additionalProperties': False,
        },
    )


def _generation_request(
    *,
    prompt: JsonValue,
    idempotency_key: str | None = None,
) -> GenerationRequest:
    return GenerationRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        model_key='nano_banana',
        operation_key='text_to_image',
        inputs={'prompt': prompt},
        idempotency_key=idempotency_key,
    )


def _existing_job() -> GenerationJob:
    now = datetime.now(UTC)
    return GenerationJob(
        id=uuid4(),
        project_id=uuid4(),
        collection_id=uuid4(),
        collection_item_id=uuid4(),
        operation_key='text_to_image',
        provider='fal',
        model_key='nano_banana',
        endpoint_id='fal-ai/nano-banana',
        status='IN_PROGRESS',
        inputs_json={'prompt': 'cat'},
        outputs_json=[],
        provider_request_id='req-existing',
        provider_response_json=None,
        idempotency_key='idem-1',
        error_code=None,
        error_message=None,
        submitted_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


def test_execute_returns_existing_idempotent_job_without_submitting() -> None:
    existing = _existing_job()
    collection_repo = FakeCollectionItemRepository()
    job_repo = FakeGenerationJobRepository(existing_by_idempotency=existing)
    provider = FakeGenerationProvider()
    capability_registry = FakeCapabilityRegistry(
        has_model=True,
        resolved_operation=_resolved_operation(),
    )
    validator = FakeInputValidator()
    use_case = SubmitGenerationJobUseCase(
        collection_repo,
        job_repo,
        provider,
        capability_registry,
        validator,
        webhook_url='https://backend.test/api/v1/provider/fal/webhook',
    )

    result = use_case.execute(_generation_request(prompt='a cat', idempotency_key='idem-1'))

    assert result == existing
    assert collection_repo.created_payload is None
    assert provider.submit_calls == []


def test_execute_raises_for_unsupported_model() -> None:
    use_case = SubmitGenerationJobUseCase(
        FakeCollectionItemRepository(),
        FakeGenerationJobRepository(),
        FakeGenerationProvider(),
        FakeCapabilityRegistry(has_model=False, resolved_operation=_resolved_operation()),
        FakeInputValidator(),
        webhook_url='https://backend.test/api/v1/provider/fal/webhook',
    )

    with pytest.raises(UnsupportedModelKeyError):
        use_case.execute(_generation_request(prompt='a cat'))


def test_execute_raises_for_unsupported_operation() -> None:
    use_case = SubmitGenerationJobUseCase(
        FakeCollectionItemRepository(),
        FakeGenerationJobRepository(),
        FakeGenerationProvider(),
        FakeCapabilityRegistry(has_model=True, resolved_operation=None),
        FakeInputValidator(),
        webhook_url='https://backend.test/api/v1/provider/fal/webhook',
    )

    with pytest.raises(UnsupportedOperationKeyError):
        use_case.execute(_generation_request(prompt='a cat'))


def test_execute_validates_inputs_and_submits_provider_job() -> None:
    collection_repo = FakeCollectionItemRepository()
    job_repo = FakeGenerationJobRepository()
    provider = FakeGenerationProvider()
    capability_registry = FakeCapabilityRegistry(
        has_model=True, resolved_operation=_resolved_operation()
    )
    validator = FakeInputValidator()
    use_case = SubmitGenerationJobUseCase(
        collection_repo,
        job_repo,
        provider,
        capability_registry,
        validator,
        webhook_url='https://backend.test/api/v1/provider/fal/webhook',
    )

    request = _generation_request(prompt='a cat')
    result = use_case.execute(request)

    assert len(validator.calls) == 1
    assert validator.calls[0]['inputs'] == request.inputs
    assert collection_repo.created_payload is not None
    assert collection_repo.created_payload.status == 'GENERATING'
    assert collection_repo.created_payload.metadata['format'] == 'png'
    assert collection_repo.assigned == [
        (collection_repo.created_item_id, job_repo.created_jobs[0].id),
    ]
    assert len(provider.submit_calls) == 1
    assert provider.submit_calls[0]['endpoint_id'] == 'fal-ai/nano-banana'
    assert result.status == 'IN_PROGRESS'
    assert result.provider_request_id == 'req-123'


def test_execute_uses_video_placeholder_metadata_format_mp4() -> None:
    collection_repo = FakeCollectionItemRepository()
    use_case = SubmitGenerationJobUseCase(
        collection_repo,
        FakeGenerationJobRepository(),
        FakeGenerationProvider(),
        FakeCapabilityRegistry(
            has_model=True, resolved_operation=_resolved_operation(media_type='video')
        ),
        FakeInputValidator(),
        webhook_url='https://backend.test/api/v1/provider/fal/webhook',
    )

    use_case.execute(_generation_request(prompt='a video prompt'))

    assert collection_repo.created_payload is not None
    assert collection_repo.created_payload.media_type == 'video'
    assert collection_repo.created_payload.metadata['format'] == 'mp4'


def test_execute_uses_default_item_name_when_prompt_missing_or_blank() -> None:
    collection_repo = FakeCollectionItemRepository()
    use_case = SubmitGenerationJobUseCase(
        collection_repo,
        FakeGenerationJobRepository(),
        FakeGenerationProvider(),
        FakeCapabilityRegistry(has_model=True, resolved_operation=_resolved_operation()),
        FakeInputValidator(),
        webhook_url='https://backend.test/api/v1/provider/fal/webhook',
    )

    use_case.execute(_generation_request(prompt=''))

    assert collection_repo.created_payload is not None
    assert collection_repo.created_payload.name == 'Generated Asset'


def test_execute_truncates_item_name_to_80_characters() -> None:
    collection_repo = FakeCollectionItemRepository()
    use_case = SubmitGenerationJobUseCase(
        collection_repo,
        FakeGenerationJobRepository(),
        FakeGenerationProvider(),
        FakeCapabilityRegistry(has_model=True, resolved_operation=_resolved_operation()),
        FakeInputValidator(),
        webhook_url='https://backend.test/api/v1/provider/fal/webhook',
    )

    long_prompt = 'x' * 120
    use_case.execute(_generation_request(prompt=long_prompt))

    assert collection_repo.created_payload is not None
    assert collection_repo.created_payload.name == 'x' * 80


def test_execute_raises_when_assign_job_id_returns_none() -> None:
    collection_repo = FakeCollectionItemRepository(assign_returns_none=True)
    use_case = SubmitGenerationJobUseCase(
        collection_repo,
        FakeGenerationJobRepository(),
        FakeGenerationProvider(),
        FakeCapabilityRegistry(has_model=True, resolved_operation=_resolved_operation()),
        FakeInputValidator(),
        webhook_url='https://backend.test/api/v1/provider/fal/webhook',
    )

    with pytest.raises(LookupError, match='not found after generation job creation'):
        use_case.execute(_generation_request(prompt='a cat'))


def test_execute_marks_job_and_item_failed_when_provider_submit_raises() -> None:
    collection_repo = FakeCollectionItemRepository()
    job_repo = FakeGenerationJobRepository()
    provider = FakeGenerationProvider(error=RuntimeError('provider down'))
    use_case = SubmitGenerationJobUseCase(
        collection_repo,
        job_repo,
        provider,
        FakeCapabilityRegistry(has_model=True, resolved_operation=_resolved_operation()),
        FakeInputValidator(),
        webhook_url='https://backend.test/api/v1/provider/fal/webhook',
    )

    with pytest.raises(RuntimeError, match='provider down'):
        use_case.execute(_generation_request(prompt='a cat'))

    assert len(job_repo.failed_calls) == 1
    assert job_repo.failed_calls[0]['error_code'] == 'provider_submit_failed'
    assert collection_repo.failed_calls == [
        (collection_repo.created_item_id, 'Failed to submit generation request'),
    ]
