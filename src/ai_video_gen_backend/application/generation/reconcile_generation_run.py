from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.application.generation.finalize_generation import GenerationFinalizer
from ai_video_gen_backend.domain.generation import (
    GeneratedOutput,
    GenerationProviderPort,
    GenerationRun,
    GenerationRunOutput,
    GenerationRunRepositoryPort,
)
from ai_video_gen_backend.domain.types import JsonObject


class ReconcileGenerationRunUseCase:
    def __init__(
        self,
        generation_run_repository: GenerationRunRepositoryPort,
        generation_provider: GenerationProviderPort,
        generation_finalizer: GenerationFinalizer,
    ) -> None:
        self._generation_run_repository = generation_run_repository
        self._generation_provider = generation_provider
        self._generation_finalizer = generation_finalizer

    def execute(self, run: GenerationRun) -> GenerationRun:
        if run.status in {'SUCCEEDED', 'PARTIAL_FAILED', 'FAILED', 'CANCELLED'}:
            return run

        if run.provider_request_id is None:
            return run

        if run.endpoint_id is None:
            return run

        provider_status = self._generation_provider.status(
            endpoint_id=run.endpoint_id,
            provider_request_id=run.provider_request_id,
        )

        if provider_status.status == 'IN_PROGRESS':
            return self._generation_run_repository.mark_run_in_progress(run.id)

        run_outputs = self._generation_run_repository.list_outputs_by_run_id(run.id)

        if provider_status.status in {'FAILED', 'CANCELLED'}:
            for run_output in run_outputs:
                if run_output.status == 'READY':
                    continue
                self._generation_finalizer.finalize_output_failure(
                    output_id=run_output.id,
                    error_code='provider_generation_failed',
                    error_message='Generation failed on provider',
                )

            if provider_status.status == 'CANCELLED':
                self._generation_run_repository.mark_run_cancelled(
                    run.id,
                    error_message='Generation was cancelled on provider',
                )
            else:
                self._generation_run_repository.mark_run_failed(
                    run.id,
                    error_code='provider_generation_failed',
                    error_message='Generation failed on provider',
                )
            return self._generation_run_repository.get_run_by_id(run.id) or run

        result = self._generation_provider.result(
            endpoint_id=run.endpoint_id,
            provider_request_id=run.provider_request_id,
        )
        outputs_by_index = {output.index: _output_to_json(output) for output in result.outputs}

        for run_output in run_outputs:
            if run_output.status in {'READY', 'FAILED'}:
                continue
            provider_output = outputs_by_index.get(run_output.output_index)
            if result.status == 'SUCCEEDED' and provider_output is not None:
                self._generation_finalizer.finalize_output_success(
                    output_id=run_output.id,
                    output=provider_output,
                )
                continue

            error_message = (
                result.error_message or 'Provider reported success without output URL'
                if result.status == 'SUCCEEDED'
                else result.error_message or 'Generation failed on provider'
            )
            self._generation_finalizer.finalize_output_failure(
                output_id=run_output.id,
                error_code='provider_generation_failed',
                error_message=error_message,
                provider_output_json=provider_output,
            )

        refreshed_outputs = self._generation_run_repository.list_outputs_by_run_id(run.id)
        self._mark_run_status_from_outputs(
            run_id=run.id,
            outputs=refreshed_outputs,
            provider_response_json=result.raw_response,
            provider_failure_message=result.error_message or 'Generation failed on provider',
        )

        refreshed = self._generation_run_repository.get_run_by_id(run.id)
        return refreshed if refreshed is not None else run

    def _mark_run_status_from_outputs(
        self,
        *,
        run_id: UUID,
        outputs: list[GenerationRunOutput],
        provider_response_json: dict[str, object],
        provider_failure_message: str,
    ) -> None:
        ready_count = sum(1 for output in outputs if output.status == 'READY')
        failed_count = sum(1 for output in outputs if output.status == 'FAILED')
        total = len(outputs)

        if total == 0:
            self._generation_run_repository.mark_run_failed(
                run_id,
                error_code='provider_generation_failed',
                error_message=provider_failure_message,
                provider_response_json=provider_response_json,
            )
            return

        if ready_count == total:
            self._generation_run_repository.mark_run_succeeded(
                run_id,
                provider_response_json=provider_response_json,
            )
            return

        if ready_count > 0 and failed_count > 0:
            self._generation_run_repository.mark_run_partial_failed(
                run_id,
                provider_response_json=provider_response_json,
                error_message='Some outputs failed',
            )
            return

        self._generation_run_repository.mark_run_failed(
            run_id,
            error_code='provider_generation_failed',
            error_message=provider_failure_message,
            provider_response_json=provider_response_json,
        )


def _output_to_json(output: GeneratedOutput) -> JsonObject:
    return {
        'index': output.index,
        'media_type': output.media_type,
        'provider_url': output.provider_url,
        'stored_url': None,
        'metadata': dict(output.metadata),
    }
