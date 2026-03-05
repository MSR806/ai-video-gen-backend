from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.generation import GenerationJob
from ai_video_gen_backend.domain.types import JsonValue
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class GenerationJobError(StrictSchema):
    code: str | None = None
    message: str | None = None


class GenerationJobResponse(StrictSchema):
    id: UUID
    status: Literal['QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED']
    operation_key: str = Field(alias='operationKey')
    provider: str
    model_key: str = Field(alias='modelKey')
    endpoint_id: str | None = Field(default=None, alias='endpointId')
    project_id: UUID = Field(alias='projectId')
    collection_id: UUID = Field(alias='collectionId')
    item_id: UUID | None = Field(default=None, alias='itemId')
    outputs: list[dict[str, JsonValue]] = Field(default_factory=list)
    error: GenerationJobError | None = None
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')
    submitted_at: datetime | None = Field(default=None, alias='submittedAt')
    completed_at: datetime | None = Field(default=None, alias='completedAt')

    @classmethod
    def from_domain(cls, job: GenerationJob) -> GenerationJobResponse:
        error: GenerationJobError | None = None
        if job.error_code is not None or job.error_message is not None:
            error = GenerationJobError(code=job.error_code, message=job.error_message)

        return cls(
            id=job.id,
            status=job.status,
            operation_key=job.operation_key,
            provider=job.provider,
            model_key=job.model_key,
            endpoint_id=job.endpoint_id,
            project_id=job.project_id,
            collection_id=job.collection_id,
            item_id=job.collection_item_id,
            outputs=[dict(output) for output in job.outputs_json],
            error=error,
            created_at=job.created_at,
            updated_at=job.updated_at,
            submitted_at=job.submitted_at,
            completed_at=job.completed_at,
        )
