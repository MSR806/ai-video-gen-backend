from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.collection_item import (
    CameraBody,
    CameraSetup,
    CollectionItem,
    FocalLength,
    GeneratedCollectionItem,
    JsonValue,
    Lens,
)
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class CollectionItemResponse(StrictSchema):
    id: UUID
    project_id: UUID = Field(alias='projectId')
    collection_id: UUID = Field(alias='collectionId')
    media_type: Literal['image', 'video'] = Field(alias='mediaType')
    name: str
    description: str
    url: str
    metadata: dict[str, JsonValue]
    generation_source: str = Field(alias='generationSource')
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
            name=item.name,
            description=item.description,
            url=item.url,
            metadata=item.metadata,
            generation_source=item.generation_source,
            storage_provider=item.storage_provider,
            storage_bucket=item.storage_bucket,
            storage_key=item.storage_key,
            mime_type=item.mime_type,
            size_bytes=item.size_bytes,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class CreateCollectionItemRequest(StrictSchema):
    project_id: UUID = Field(alias='projectId')
    media_type: Literal['image', 'video'] = Field(alias='mediaType')
    name: str
    description: str
    url: str
    metadata: dict[str, JsonValue]
    generation_source: str = Field(default='upload', alias='generationSource')


class CameraBodySchema(StrictSchema):
    id: str
    name: str
    type: Literal['cinema', 'dslr', 'mirrorless']

    def to_domain(self) -> CameraBody:
        return CameraBody(id=self.id, name=self.name, type=self.type)


class LensSchema(StrictSchema):
    id: str
    name: str
    brand: str
    type: Literal['prime', 'zoom']

    def to_domain(self) -> Lens:
        return Lens(id=self.id, name=self.name, brand=self.brand, type=self.type)


class FocalLengthSchema(StrictSchema):
    value: int
    label: str
    category: Literal['ultra-wide', 'wide', 'standard', 'portrait', 'telephoto']

    def to_domain(self) -> FocalLength:
        return FocalLength(value=self.value, label=self.label, category=self.category)


class CameraSetupSchema(StrictSchema):
    camera: CameraBodySchema
    lens: LensSchema
    focal_length: FocalLengthSchema = Field(alias='focalLength')

    def to_domain(self) -> CameraSetup:
        return CameraSetup(
            camera=self.camera.to_domain(),
            lens=self.lens.to_domain(),
            focal_length=self.focal_length.to_domain(),
        )


class GenerateCollectionItemRequest(StrictSchema):
    prompt: str
    aspect_ratio: Literal['square', 'portrait', 'landscape'] = Field(alias='aspectRatio')
    media_type: Literal['image', 'video'] = Field(alias='mediaType')
    project_id: UUID = Field(alias='projectId')
    reference_images: list[str] | None = Field(default=None, alias='referenceImages')
    camera_setup: CameraSetupSchema | None = Field(default=None, alias='cameraSetup')
    resolution: Literal['2k', '4k', '8k'] | None = None
    batch_size: Literal[1, 2, 3, 4] | None = Field(default=None, alias='batchSize')


class GeneratedCollectionItemResponse(StrictSchema):
    url: str
    thumbnail_url: str = Field(alias='thumbnailUrl')
    width: int
    height: int
    format: str
    duration: int | None = None

    @classmethod
    def from_domain(cls, item: GeneratedCollectionItem) -> GeneratedCollectionItemResponse:
        return cls(
            url=item.url,
            thumbnail_url=item.thumbnail_url,
            width=item.width,
            height=item.height,
            format=item.format,
            duration=item.duration,
        )
