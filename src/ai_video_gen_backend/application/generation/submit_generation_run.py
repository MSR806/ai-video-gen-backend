from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.application.generation.validate_generation_inputs import (
    GenerationInputValidator,
)
from ai_video_gen_backend.domain.collection_item import (
    CollectionItemCreationPayload,
    CollectionItemRepositoryPort,
)
from ai_video_gen_backend.domain.generation import (
    GenerationCapabilityRegistryPort,
    GenerationProviderPort,
    GenerationRunRepositoryPort,
    GenerationRunRequest,
    GenerationRunSubmission,
    SubmittedRunOutput,
)
from ai_video_gen_backend.domain.types import JsonObject


class UnsupportedModelKeyError(Exception):
    """Raised when model key is not allowed."""


class UnsupportedOperationKeyError(Exception):
    """Raised when operation key is not supported for the selected model."""


class UnsupportedBatchOutputCountError(Exception):
    """Raised when requested output count is not supported for the selected operation."""


class InvalidOutputCountError(Exception):
    """Raised when requested output count is outside allowed bounds."""


class SubmitGenerationRunUseCase:
    def __init__(
        self,
        collection_item_repository: CollectionItemRepositoryPort,
        generation_run_repository: GenerationRunRepositoryPort,
        generation_provider: GenerationProviderPort,
        capability_registry: GenerationCapabilityRegistryPort,
        input_validator: GenerationInputValidator,
        *,
        webhook_url: str,
        max_output_count: int = 4,
    ) -> None:
        self._collection_item_repository = collection_item_repository
        self._generation_run_repository = generation_run_repository
        self._generation_provider = generation_provider
        self._capability_registry = capability_registry
        self._input_validator = input_validator
        self._webhook_url = webhook_url
        self._max_output_count = max_output_count

    def execute(self, request: GenerationRunRequest) -> GenerationRunSubmission:
        output_count = request.output_count
        if output_count < 1 or output_count > self._max_output_count:
            raise InvalidOutputCountError

        if request.idempotency_key is not None:
            existing_run = self._generation_run_repository.get_run_by_idempotency_key(
                project_id=request.project_id,
                idempotency_key=request.idempotency_key,
            )
            if existing_run is not None:
                existing_outputs = self._generation_run_repository.list_outputs_by_run_id(
                    existing_run.id
                )
                existing_items = self._collection_item_repository.get_items_by_run_id(
                    existing_run.id
                )
                item_by_output_id = {
                    item.generation_run_output_id: item
                    for item in existing_items
                    if item.generation_run_output_id is not None
                }
                return GenerationRunSubmission(
                    run=existing_run,
                    outputs=[
                        SubmittedRunOutput(
                            output_id=output.id,
                            output_index=output.output_index,
                            status=output.status,
                            collection_item_id=item_by_output_id[output.id].id,
                        )
                        for output in existing_outputs
                        if output.id in item_by_output_id
                    ],
                )

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

        if output_count > 1 and not _supports_native_batch(resolved_operation.input_schema):
            raise UnsupportedBatchOutputCountError

        provider_inputs = dict(request.inputs)
        if _supports_native_batch(resolved_operation.input_schema):
            provider_inputs['num_images'] = output_count

        generation_run = self._generation_run_repository.create_run(
            project_id=request.project_id,
            operation_key=request.operation_key,
            provider=resolved_operation.provider,
            model_key=request.model_key,
            endpoint_id=resolved_operation.endpoint_id,
            requested_output_count=output_count,
            inputs_json=request.inputs,
            idempotency_key=request.idempotency_key,
        )

        outputs = self._generation_run_repository.create_run_outputs(
            run_id=generation_run.id,
            output_count=output_count,
        )

        submitted_outputs: list[SubmittedRunOutput] = []
        for output in outputs:
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
                        output_index=output.output_index,
                    ),
                    generation_source='fal',
                    status='GENERATING',
                    run_id=generation_run.id,
                    generation_run_output_id=output.id,
                )
            )
            submitted_outputs.append(
                SubmittedRunOutput(
                    output_id=output.id,
                    output_index=output.output_index,
                    status=output.status,
                    collection_item_id=placeholder_item.id,
                )
            )

        try:
            submission = self._generation_provider.submit(
                endpoint_id=resolved_operation.endpoint_id,
                inputs=provider_inputs,
                webhook_url=self._webhook_url,
            )
            submitted_run = self._generation_run_repository.mark_run_submitted(
                generation_run.id,
                provider_request_id=submission.provider_request_id,
            )
            return GenerationRunSubmission(run=submitted_run, outputs=submitted_outputs)
        except Exception as exc:
            self._generation_run_repository.mark_run_failed(
                generation_run.id,
                error_code='provider_submit_failed',
                error_message=str(exc),
            )
            for output in outputs:
                self._collection_item_repository.mark_generated_item_failed(
                    item_id=self._submitted_item_id(
                        output_id=output.id, submitted_outputs=submitted_outputs
                    ),
                    error_message='Failed to submit generation request',
                )
                self._generation_run_repository.mark_output_failed(
                    output_id=output.id,
                    error_code='provider_submit_failed',
                    error_message='Failed to submit generation request',
                )
            raise

    def _submitted_item_id(
        self, *, output_id: UUID, submitted_outputs: list[SubmittedRunOutput]
    ) -> UUID:
        for submitted_output in submitted_outputs:
            if submitted_output.output_id == output_id:
                return submitted_output.collection_item_id
        msg = f'Collection item placeholder missing for output {output_id}'
        raise LookupError(msg)

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
        output_index: int,
    ) -> JsonObject:
        default_format = 'mp4' if media_type == 'video' else 'png'
        return {
            'operationKey': operation_key,
            'modelKey': model_key,
            'thumbnailUrl': '',
            'width': 0,
            'height': 0,
            'format': default_format,
            'outputIndex': output_index,
        }


def _supports_native_batch(input_schema: JsonObject) -> bool:
    properties = input_schema.get('properties')
    if not isinstance(properties, dict):
        return False

    num_images = properties.get('num_images')
    if not isinstance(num_images, dict):
        return False

    field_type = num_images.get('type')
    return field_type == 'integer'
