from __future__ import annotations

from ai_video_gen_backend.application.generation.finalize_generation import GenerationFinalizer
from ai_video_gen_backend.domain.generation import (
    GeneratedOutput,
    GenerationJob,
    GenerationJobRepositoryPort,
    GenerationProviderPort,
)
from ai_video_gen_backend.domain.types import JsonObject


class ReconcileGenerationJobUseCase:
    def __init__(
        self,
        generation_job_repository: GenerationJobRepositoryPort,
        generation_provider: GenerationProviderPort,
        generation_finalizer: GenerationFinalizer,
    ) -> None:
        self._generation_job_repository = generation_job_repository
        self._generation_provider = generation_provider
        self._generation_finalizer = generation_finalizer

    def execute(self, job: GenerationJob) -> GenerationJob:
        if job.status in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:
            return job

        if job.provider_request_id is None:
            return job

        if job.endpoint_id is None:
            return job

        provider_status = self._generation_provider.status(
            endpoint_id=job.endpoint_id,
            provider_request_id=job.provider_request_id,
        )

        if provider_status.status == 'IN_PROGRESS':
            return self._generation_job_repository.mark_in_progress(job.id)

        if provider_status.status in {'FAILED', 'CANCELLED'}:
            if job.collection_item_id is not None:
                self._generation_finalizer.finalize_failure(
                    job_id=job.id,
                    item_id=job.collection_item_id,
                    error_code='provider_generation_failed',
                    error_message='Generation failed on provider',
                )
            return self._generation_job_repository.get_by_id(job.id) or job

        result = self._generation_provider.result(
            endpoint_id=job.endpoint_id,
            provider_request_id=job.provider_request_id,
        )
        outputs_json = [_output_to_json(output) for output in result.outputs]
        if (
            result.status == 'SUCCEEDED'
            and len(outputs_json) > 0
            and job.collection_item_id is not None
        ):
            self._generation_finalizer.finalize_success(
                job_id=job.id,
                item_id=job.collection_item_id,
                output=outputs_json[0],
                provider_response_json=result.raw_response,
                outputs_json=outputs_json,
            )
            refreshed = self._generation_job_repository.get_by_id(job.id)
            return refreshed if refreshed is not None else job

        if job.collection_item_id is not None:
            self._generation_finalizer.finalize_failure(
                job_id=job.id,
                item_id=job.collection_item_id,
                error_code='provider_generation_failed',
                error_message=result.error_message or 'Generation failed on provider',
                provider_response_json=result.raw_response,
            )

        refreshed = self._generation_job_repository.get_by_id(job.id)
        return refreshed if refreshed is not None else job


def _output_to_json(output: GeneratedOutput) -> JsonObject:
    return {
        'index': output.index,
        'media_type': output.media_type,
        'provider_url': output.provider_url,
        'stored_url': None,
        'metadata': dict(output.metadata),
    }
