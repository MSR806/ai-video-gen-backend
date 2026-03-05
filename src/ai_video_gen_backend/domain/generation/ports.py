from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .capabilities import GenerationCapabilities, ResolvedGenerationOperation
from .entities import (
    GenerationJob,
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


class GenerationJobRepositoryPort(Protocol):
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
    ) -> GenerationJob: ...

    def get_by_id(self, job_id: UUID) -> GenerationJob | None: ...

    def get_by_provider_request_id(self, provider_request_id: str) -> GenerationJob | None: ...

    def get_by_idempotency_key(
        self,
        *,
        project_id: UUID,
        collection_id: UUID,
        idempotency_key: str,
    ) -> GenerationJob | None: ...

    def mark_submitted(self, job_id: UUID, *, provider_request_id: str) -> GenerationJob: ...

    def mark_in_progress(self, job_id: UUID) -> GenerationJob: ...

    def mark_succeeded(
        self,
        job_id: UUID,
        *,
        provider_response_json: dict[str, object],
        outputs_json: list[dict[str, object]],
    ) -> GenerationJob: ...

    def mark_failed(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationJob: ...
