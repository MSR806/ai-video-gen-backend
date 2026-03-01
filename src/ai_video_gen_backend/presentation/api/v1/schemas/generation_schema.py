from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ai_video_gen_backend.domain.generation import GenerationJob
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class GenerateCollectionItemRequest(StrictSchema):
    project_id: UUID = Field(alias='projectId')
    operation: Literal['TEXT_TO_IMAGE', 'IMAGE_TO_IMAGE']
    prompt: str
    source_image_urls: list[str] | None = Field(default=None, alias='sourceImageUrls')
    model_key: str | None = Field(default=None, alias='modelKey')
    aspect_ratio: Literal['SQUARE', 'PORTRAIT', 'LANDSCAPE'] = Field(
        default='LANDSCAPE', alias='aspectRatio'
    )
    seed: int | None = None
    idempotency_key: str | None = Field(default=None, alias='idempotencyKey')

    @model_validator(mode='after')
    def validate_operation_payload(self) -> GenerateCollectionItemRequest:
        if self.operation == 'IMAGE_TO_IMAGE' and (
            self.source_image_urls is None or len(self.source_image_urls) != 1
        ):
            raise ValueError('image_to_image requires exactly one source image URL')

        if self.operation == 'TEXT_TO_IMAGE' and self.source_image_urls not in (None, []):
            raise ValueError('text_to_image does not accept sourceImageUrls')

        return self


class SubmitGenerationResponse(StrictSchema):
    job_id: UUID = Field(alias='jobId')
    item_id: UUID = Field(alias='itemId')
    status: Literal['QUEUED', 'IN_PROGRESS']


class GenerationJobError(StrictSchema):
    code: str | None = None
    message: str | None = None


class GenerationJobResponse(StrictSchema):
    id: UUID
    status: Literal['QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED']
    operation: Literal['TEXT_TO_IMAGE', 'IMAGE_TO_IMAGE']
    provider: str
    model_key: str = Field(alias='modelKey')
    project_id: UUID = Field(alias='projectId')
    collection_id: UUID = Field(alias='collectionId')
    item_id: UUID | None = Field(default=None, alias='itemId')
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
            operation=job.operation,
            provider=job.provider,
            model_key=job.model_key,
            project_id=job.project_id,
            collection_id=job.collection_id,
            item_id=job.collection_item_id,
            error=error,
            created_at=job.created_at,
            updated_at=job.updated_at,
            submitted_at=job.submitted_at,
            completed_at=job.completed_at,
        )
