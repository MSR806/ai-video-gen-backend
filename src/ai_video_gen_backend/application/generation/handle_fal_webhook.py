from __future__ import annotations

from ai_video_gen_backend.application.generation.finalize_generation import (
    GenerationFinalizationError,
    GenerationFinalizer,
)
from ai_video_gen_backend.domain.generation import (
    GeneratedOutput,
    GenerationJobRepositoryPort,
    GenerationProviderPort,
)
from ai_video_gen_backend.domain.types import JsonObject


class HandleFalWebhookUseCase:
    def __init__(
        self,
        generation_job_repository: GenerationJobRepositoryPort,
        generation_provider: GenerationProviderPort,
        generation_finalizer: GenerationFinalizer,
    ) -> None:
        self._generation_job_repository = generation_job_repository
        self._generation_provider = generation_provider
        self._generation_finalizer = generation_finalizer

    def execute(self, payload: dict[str, object]) -> bool:
        event = self._generation_provider.parse_webhook(payload)
        if event is None:
            return False

        job = self._generation_job_repository.get_by_provider_request_id(event.provider_request_id)
        if job is None:
            return False

        if job.status in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:
            return True

        if job.collection_item_id is None:
            raise GenerationFinalizationError('Generation job has no linked collection item')

        if event.status == 'SUCCEEDED':
            outputs_json = [_output_to_json(output) for output in event.outputs]
            provider_response_json = event.raw_response

            if (
                len(outputs_json) == 0
                and job.provider_request_id is not None
                and job.endpoint_id is not None
            ):
                result = self._generation_provider.result(
                    endpoint_id=job.endpoint_id,
                    provider_request_id=job.provider_request_id,
                )
                provider_response_json = result.raw_response
                if result.status == 'SUCCEEDED':
                    outputs_json = [_output_to_json(output) for output in result.outputs]
                else:
                    error_message = result.error_message or 'Generation failed'
                    self._generation_finalizer.finalize_failure(
                        job_id=job.id,
                        item_id=job.collection_item_id,
                        error_code='provider_generation_failed',
                        error_message=error_message,
                        provider_response_json=provider_response_json,
                    )
                    return True

            if len(outputs_json) > 0:
                self._generation_finalizer.finalize_success(
                    job_id=job.id,
                    item_id=job.collection_item_id,
                    output=outputs_json[0],
                    provider_response_json=provider_response_json,
                    outputs_json=outputs_json,
                )
                return True

            self._generation_finalizer.finalize_failure(
                job_id=job.id,
                item_id=job.collection_item_id,
                error_code='provider_generation_failed',
                error_message='Provider reported success without output URL',
                provider_response_json=provider_response_json,
            )
            return True

        error_message = event.error_message or 'Generation failed'
        self._generation_finalizer.finalize_failure(
            job_id=job.id,
            item_id=job.collection_item_id,
            error_code='provider_generation_failed',
            error_message=error_message,
            provider_response_json=event.raw_response,
        )
        return True


def _output_to_json(output: GeneratedOutput) -> JsonObject:
    return {
        'index': output.index,
        'media_type': output.media_type,
        'provider_url': output.provider_url,
        'stored_url': None,
        'metadata': dict(output.metadata),
    }
