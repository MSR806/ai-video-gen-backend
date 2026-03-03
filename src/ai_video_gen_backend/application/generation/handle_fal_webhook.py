from __future__ import annotations

from ai_video_gen_backend.application.generation.finalize_generation import (
    GenerationFinalizationError,
    GenerationFinalizer,
)
from ai_video_gen_backend.domain.generation import (
    GenerationJobRepositoryPort,
    GenerationProviderPort,
)


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
            output_url = event.output_url
            provider_response = event.raw_response

            if output_url is None and job.provider_request_id is not None:
                result = self._generation_provider.result(
                    model_key=job.model_key,
                    provider_request_id=job.provider_request_id,
                )
                provider_response = result.raw_response
                if result.status == 'SUCCEEDED':
                    output_url = result.output_url
                else:
                    error_message = result.error_message or 'Generation failed'
                    self._generation_finalizer.finalize_failure(
                        job_id=job.id,
                        item_id=job.collection_item_id,
                        error_code='provider_generation_failed',
                        error_message=error_message,
                        provider_response=provider_response,
                    )
                    return True

            if output_url is not None:
                self._generation_finalizer.finalize_success(
                    job_id=job.id,
                    item_id=job.collection_item_id,
                    output_url=output_url,
                    provider_response=provider_response,
                )
                return True

            self._generation_finalizer.finalize_failure(
                job_id=job.id,
                item_id=job.collection_item_id,
                error_code='provider_generation_failed',
                error_message='Provider reported success without output URL',
                provider_response=provider_response,
            )
            return True

        error_message = event.error_message or 'Generation failed'
        self._generation_finalizer.finalize_failure(
            job_id=job.id,
            item_id=job.collection_item_id,
            error_code='provider_generation_failed',
            error_message=error_message,
            provider_response=event.raw_response,
        )
        return True
