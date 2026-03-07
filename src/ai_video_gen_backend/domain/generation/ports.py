from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .capabilities import GenerationCapabilities, ResolvedGenerationOperation
from .entities import (
    GenerationRun,
    GenerationRunOutput,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
)


class GenerationCapabilityRegistryPort(Protocol):
    def list_capabilities(self) -> GenerationCapabilities: ...

    def has_model(self, *, model_key: str) -> bool: ...

    def resolve_operation(
        self, *, model_key: str, operation_key: str
    ) -> ResolvedGenerationOperation | None: ...


class GenerationProviderPort(Protocol):
    def submit(
        self,
        *,
        endpoint_id: str,
        inputs: dict[str, object],
        webhook_url: str,
    ) -> ProviderSubmission: ...

    def status(self, *, endpoint_id: str, provider_request_id: str) -> ProviderStatus: ...

    def result(
        self,
        *,
        endpoint_id: str,
        provider_request_id: str,
    ) -> ProviderResult: ...

    def cancel(self, *, endpoint_id: str, provider_request_id: str) -> None: ...

    def parse_webhook(self, payload: dict[str, object]) -> ProviderWebhookEvent | None: ...


class GenerationRunRepositoryPort(Protocol):
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
    ) -> GenerationRun: ...

    def create_run_outputs(
        self, *, run_id: UUID, output_count: int
    ) -> list[GenerationRunOutput]: ...

    def get_run_by_id(self, run_id: UUID) -> GenerationRun | None: ...

    def get_run_by_provider_request_id(self, provider_request_id: str) -> GenerationRun | None: ...

    def get_run_by_idempotency_key(
        self,
        *,
        project_id: UUID,
        idempotency_key: str,
    ) -> GenerationRun | None: ...

    def list_outputs_by_run_id(self, run_id: UUID) -> list[GenerationRunOutput]: ...

    def mark_run_submitted(self, run_id: UUID, *, provider_request_id: str) -> GenerationRun: ...

    def mark_run_in_progress(self, run_id: UUID) -> GenerationRun: ...

    def mark_run_succeeded(
        self,
        run_id: UUID,
        *,
        provider_response_json: dict[str, object],
    ) -> GenerationRun: ...

    def mark_run_partial_failed(
        self,
        run_id: UUID,
        *,
        provider_response_json: dict[str, object],
        error_message: str,
    ) -> GenerationRun: ...

    def mark_run_failed(
        self,
        run_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun: ...

    def mark_run_cancelled(
        self,
        run_id: UUID,
        *,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun: ...

    def mark_output_ready(
        self,
        *,
        output_id: UUID,
        provider_output_json: dict[str, object],
        stored_output_json: dict[str, object],
    ) -> GenerationRunOutput: ...

    def mark_output_failed(
        self,
        *,
        output_id: UUID,
        error_code: str,
        error_message: str,
        provider_output_json: dict[str, object] | None = None,
    ) -> GenerationRunOutput: ...
