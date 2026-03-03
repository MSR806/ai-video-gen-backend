from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    JsonValue,
)
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class CollectionItemResponse(StrictSchema):
    id: UUID
    project_id: UUID = Field(alias='projectId')
    collection_id: UUID = Field(alias='collectionId')
    media_type: Literal['image', 'video'] = Field(alias='mediaType')
    status: Literal['GENERATING', 'READY', 'FAILED']
    name: str
    description: str
    url: str | None
    metadata: dict[str, JsonValue]
    generation_source: str = Field(alias='generationSource')
    generation_error_message: str | None = Field(default=None, alias='generationErrorMessage')
    job_id: UUID | None = Field(default=None, alias='jobId')
    storage_provider: str | None = Field(default=None, alias='storageProvider')
    storage_bucket: str | None = Field(default=None, alias='storageBucket')
    storage_key: str | None = Field(default=None, alias='storageKey')
    mime_type: str | None = Field(default=None, alias='mimeType')
    size_bytes: int | None = Field(default=None, alias='sizeBytes')
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')

    @classmethod
    def from_domain(cls, item: CollectionItem) -> CollectionItemResponse:
        return cls(
            id=item.id,
            project_id=item.project_id,
            collection_id=item.collection_id,
            media_type=item.media_type,
            status=item.status,
            name=item.name,
            description=item.description,
            url=item.url,
            metadata=item.metadata,
            generation_source=item.generation_source,
            generation_error_message=item.generation_error_message,
            job_id=item.job_id,
            storage_provider=item.storage_provider,
            storage_bucket=item.storage_bucket,
            storage_key=item.storage_key,
            mime_type=item.mime_type,
            size_bytes=item.size_bytes,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class CollectionItemReadResponse(StrictSchema):
    id: UUID
    project_id: UUID = Field(alias='projectId')
    collection_id: UUID = Field(alias='collectionId')
    media_type: Literal['image', 'video'] = Field(alias='mediaType')
    status: Literal['GENERATING', 'READY', 'FAILED']
    name: str
    description: str
    url: str | None
    metadata: dict[str, JsonValue]
    generation_error_message: str | None = Field(default=None, alias='generationErrorMessage')
    job_id: UUID | None = Field(default=None, alias='jobId')

    @classmethod
    def from_domain(cls, item: CollectionItem) -> CollectionItemReadResponse:
        return cls(
            id=item.id,
            project_id=item.project_id,
            collection_id=item.collection_id,
            media_type=item.media_type,
            status=item.status,
            name=item.name,
            description=item.description,
            url=item.url,
            metadata=item.metadata,
            generation_error_message=item.generation_error_message,
            job_id=item.job_id,
        )


class CreateCollectionItemRequest(StrictSchema):
    project_id: UUID = Field(alias='projectId')
    media_type: Literal['image', 'video'] = Field(alias='mediaType')
    name: str
    description: str
    url: str
    metadata: dict[str, JsonValue]
    generation_source: str = Field(default='upload', alias='generationSource')
