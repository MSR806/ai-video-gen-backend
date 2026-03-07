from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.application.generation.finalize_generation import GenerationFinalizer
from ai_video_gen_backend.domain.generation import (
    GeneratedOutput,
    GenerationProviderPort,
    GenerationRunOutput,
    GenerationRunRepositoryPort,
)
from ai_video_gen_backend.domain.types import JsonObject


class HandleFalWebhookUseCase:
    def __init__(
        self,
        generation_run_repository: GenerationRunRepositoryPort,
        generation_provider: GenerationProviderPort,
        generation_finalizer: GenerationFinalizer,
    ) -> None:
        self._generation_run_repository = generation_run_repository
        self._generation_provider = generation_provider
        self._generation_finalizer = generation_finalizer

    def execute(self, payload: dict[str, object]) -> bool:
        event = self._generation_provider.parse_webhook(payload)
        if event is None:
            return False

        run = self._generation_run_repository.get_run_by_provider_request_id(
            event.provider_request_id
        )
        if run is None:
            return False

        if run.status in {'SUCCEEDED', 'PARTIAL_FAILED', 'FAILED', 'CANCELLED'}:
            return True

        run_outputs = self._generation_run_repository.list_outputs_by_run_id(run.id)

        if event.status == 'SUCCEEDED':
            outputs_json = [_output_to_json(output) for output in event.outputs]
            provider_response_json = event.raw_response

            if (
                len(outputs_json) == 0
                and run.provider_request_id is not None
                and run.endpoint_id is not None
            ):
                result = self._generation_provider.result(
                    endpoint_id=run.endpoint_id,
                    provider_request_id=run.provider_request_id,
                )
                provider_response_json = result.raw_response
                if result.status == 'SUCCEEDED':
                    outputs_json = [_output_to_json(output) for output in result.outputs]
                else:
                    self._mark_all_outputs_failed(
                        run_outputs=run_outputs,
                        error_message=result.error_message or 'Generation failed',
                    )
                    self._generation_run_repository.mark_run_failed(
                        run.id,
                        error_code='provider_generation_failed',
                        error_message=result.error_message or 'Generation failed',
                        provider_response_json=provider_response_json,
                    )
                    return True

            output_by_index: dict[int, JsonObject] = {}
            for output in outputs_json:
                raw_index = output.get('index')
                if isinstance(raw_index, int):
                    output_by_index[raw_index] = output

            for run_output in run_outputs:
                provider_output = output_by_index.get(run_output.output_index)
                if provider_output is None:
                    self._generation_finalizer.finalize_output_failure(
                        output_id=run_output.id,
                        error_code='provider_generation_failed',
                        error_message='Provider did not return this output index',
                    )
                    continue

                self._generation_finalizer.finalize_output_success(
                    output_id=run_output.id,
                    output=provider_output,
                )

            refreshed_outputs = self._generation_run_repository.list_outputs_by_run_id(run.id)
            self._mark_run_status_from_outputs(
                run_id=run.id,
                outputs=refreshed_outputs,
                provider_response_json=provider_response_json,
            )
            return True

        error_message = event.error_message or 'Generation failed'
        self._mark_all_outputs_failed(run_outputs=run_outputs, error_message=error_message)
        self._generation_run_repository.mark_run_failed(
            run.id,
            error_code='provider_generation_failed',
            error_message=error_message,
            provider_response_json=event.raw_response,
        )
        return True

    def _mark_all_outputs_failed(
        self, *, run_outputs: list[GenerationRunOutput], error_message: str
    ) -> None:
        for run_output in run_outputs:
            if run_output.status == 'READY':
                continue
            self._generation_finalizer.finalize_output_failure(
                output_id=run_output.id,
                error_code='provider_generation_failed',
                error_message=error_message,
            )

    def _mark_run_status_from_outputs(
        self,
        *,
        run_id: UUID,
        outputs: list[GenerationRunOutput],
        provider_response_json: dict[str, object],
    ) -> None:
        ready_count = sum(1 for output in outputs if output.status == 'READY')
        failed_count = sum(1 for output in outputs if output.status == 'FAILED')
        total = len(outputs)
        if total == 0:
            self._generation_run_repository.mark_run_failed(
                run_id,
                error_code='provider_generation_failed',
                error_message='Provider reported success without outputs',
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
            error_message='Provider output finalization failed',
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
