from __future__ import annotations

from ai_video_gen_backend.application.generation.validate_generation_inputs import (
    GenerationInputValidator,
)
from ai_video_gen_backend.domain.collection_item import (
    CollectionItemCreationPayload,
    CollectionItemRepositoryPort,
)
from ai_video_gen_backend.domain.generation import (
    GenerationCapabilityRegistryPort,
    GenerationJob,
    GenerationJobRepositoryPort,
    GenerationProviderPort,
    GenerationRequest,
)
from ai_video_gen_backend.domain.types import JsonObject


class UnsupportedModelKeyError(Exception):
    """Raised when model key is not allowed."""


class UnsupportedOperationKeyError(Exception):
    """Raised when operation key is not supported for the selected model."""


class SubmitGenerationJobUseCase:
    def __init__(
        self,
        collection_item_repository: CollectionItemRepositoryPort,
        generation_job_repository: GenerationJobRepositoryPort,
        generation_provider: GenerationProviderPort,
        capability_registry: GenerationCapabilityRegistryPort,
        input_validator: GenerationInputValidator,
        *,
        webhook_url: str,
    ) -> None:
        self._collection_item_repository = collection_item_repository
        self._generation_job_repository = generation_job_repository
        self._generation_provider = generation_provider
        self._capability_registry = capability_registry
        self._input_validator = input_validator
        self._webhook_url = webhook_url

    def execute(self, request: GenerationRequest) -> GenerationJob:
        if request.idempotency_key is not None:
            existing_job = self._generation_job_repository.get_by_idempotency_key(
                project_id=request.project_id,
                collection_id=request.collection_id,
                idempotency_key=request.idempotency_key,
            )
            if existing_job is not None:
                return existing_job

        if not self._capability_registry.has_model(model_key=request.model_key):
            raise UnsupportedModelKeyError

        resolved_operation = self._capability_registry.resolve_operation(
            model_key=request.model_key,
            operation_key=request.operation_key,
        )
        if resolved_operation is None:
            raise UnsupportedOperationKeyError

        self._input_validator.validate(
            inputs=request.inputs, schema=resolved_operation.input_schema
        )

        placeholder_item = self._collection_item_repository.create_item(
            CollectionItemCreationPayload(
                project_id=request.project_id,
                collection_id=request.collection_id,
                media_type=resolved_operation.media_type,
                name=self._item_name(request.inputs),
                description='AI generation in progress',
                url=None,
                metadata=self._placeholder_metadata(
                    model_key=request.model_key,
                    operation_key=request.operation_key,
                    media_type=resolved_operation.media_type,
                ),
                generation_source='fal',
                status='GENERATING',
            )
        )

        generation_job = self._generation_job_repository.create_job(
            project_id=request.project_id,
            collection_id=request.collection_id,
            collection_item_id=placeholder_item.id,
            operation_key=request.operation_key,
            provider=resolved_operation.provider,
            model_key=request.model_key,
            endpoint_id=resolved_operation.endpoint_id,
            inputs_json=request.inputs,
            idempotency_key=request.idempotency_key,
        )

        linked_item = self._collection_item_repository.assign_job_id(
            item_id=placeholder_item.id,
            job_id=generation_job.id,
        )
        if linked_item is None:
            msg = f'Collection item {placeholder_item.id} not found after generation job creation'
            raise LookupError(msg)

        try:
            submission = self._generation_provider.submit(
                endpoint_id=resolved_operation.endpoint_id,
                inputs=request.inputs,
                webhook_url=self._webhook_url,
            )
            return self._generation_job_repository.mark_submitted(
                generation_job.id,
                provider_request_id=submission.provider_request_id,
            )
        except Exception as exc:
            self._generation_job_repository.mark_failed(
                generation_job.id,
                error_code='provider_submit_failed',
                error_message=str(exc),
            )
            self._collection_item_repository.mark_generated_item_failed(
                item_id=placeholder_item.id,
                error_message='Failed to submit generation request',
            )
            raise

    def _item_name(self, inputs: JsonObject) -> str:
        prompt_raw = inputs.get('prompt')
        if not isinstance(prompt_raw, str):
            return 'Generated Asset'

        trimmed = prompt_raw.strip()
        if len(trimmed) == 0:
            return 'Generated Asset'
        return trimmed[:80]

    def _placeholder_metadata(
        self,
        *,
        model_key: str,
        operation_key: str,
        media_type: str,
    ) -> JsonObject:
        default_format = 'mp4' if media_type == 'video' else 'png'
        return {
            'operationKey': operation_key,
            'modelKey': model_key,
            'thumbnailUrl': '',
            'width': 0,
            'height': 0,
            'format': default_format,
        }
