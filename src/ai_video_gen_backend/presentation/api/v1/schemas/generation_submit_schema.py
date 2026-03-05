from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.generation import GenerationJob
from ai_video_gen_backend.domain.types import JsonValue
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class GenerationSubmitRequest(StrictSchema):
    project_id: UUID = Field(alias='projectId')
    model_key: str = Field(alias='modelKey')
    operation_key: str = Field(alias='operationKey')
    inputs: dict[str, JsonValue]
    idempotency_key: str | None = Field(default=None, alias='idempotencyKey')


class GenerationSubmitResponse(StrictSchema):
    job_id: UUID = Field(alias='jobId')
    status: Literal['QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED']
    model_key: str = Field(alias='modelKey')
    operation_key: str = Field(alias='operationKey')

    @classmethod
    def from_domain(cls, job: GenerationJob) -> GenerationSubmitResponse:
        return cls(
            job_id=job.id,
            status=job.status,
            model_key=job.model_key,
            operation_key=job.operation_key,
        )
