from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import (
    GenerationJob,
    GenerationRequest,
    GenerationStatus,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
)


class GenerationProviderPort(Protocol):
    def submit(self, request: GenerationRequest, *, webhook_url: str) -> ProviderSubmission: ...

    def status(self, *, endpoint_id: str, provider_request_id: str) -> ProviderStatus: ...

    def result(
        self,
        *,
        endpoint_id: str,
        provider_request_id: str,
        model_key: str | None = None,
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
        operation: str,
        provider: str,
        model_key: str,
        request_payload: dict[str, object],
    ) -> GenerationJob: ...

    def get_by_id(self, job_id: UUID) -> GenerationJob | None: ...

    def get_by_provider_request_id(self, provider_request_id: str) -> GenerationJob | None: ...

    def list_jobs(
        self,
        *,
        collection_id: UUID | None = None,
        project_id: UUID | None = None,
        statuses: list[GenerationStatus] | None = None,
        limit: int = 50,
    ) -> list[GenerationJob]: ...

    def mark_submitted(self, job_id: UUID, *, provider_request_id: str) -> GenerationJob: ...

    def mark_in_progress(self, job_id: UUID) -> GenerationJob: ...

    def mark_succeeded(
        self,
        job_id: UUID,
        *,
        provider_response: dict[str, object],
    ) -> GenerationJob: ...

    def mark_failed(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response: dict[str, object] | None = None,
    ) -> GenerationJob: ...
