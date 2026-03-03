from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

JsonValue = object
JsonObject = dict[str, JsonValue]

MediaType = Literal['image', 'video']
CollectionItemStatus = Literal['GENERATING', 'READY', 'FAILED']
AspectRatio = Literal['SQUARE', 'PORTRAIT', 'LANDSCAPE']
Resolution = Literal['2k', '4k', '8k']
BatchSize = Literal[1, 2, 3, 4]


@dataclass(frozen=True, slots=True)
class CameraBody:
    id: str
    name: str
    type: Literal['cinema', 'dslr', 'mirrorless']


@dataclass(frozen=True, slots=True)
class Lens:
    id: str
    name: str
    brand: str
    type: Literal['prime', 'zoom']


@dataclass(frozen=True, slots=True)
class FocalLength:
    value: int
    label: str
    category: Literal['ultra-wide', 'wide', 'standard', 'portrait', 'telephoto']


@dataclass(frozen=True, slots=True)
class CameraSetup:
    camera: CameraBody
    lens: Lens
    focal_length: FocalLength


@dataclass(frozen=True, slots=True)
class CollectionItem:
    id: UUID
    project_id: UUID
    collection_id: UUID
    media_type: MediaType
    status: CollectionItemStatus
    name: str
    description: str
    url: str | None
    metadata: JsonObject
    generation_source: str
    generation_error_message: str | None
    created_at: datetime
    updated_at: datetime
    job_id: UUID | None = None
    storage_provider: str | None = None
    storage_bucket: str | None = None
    storage_key: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class CollectionItemCreationPayload:
    project_id: UUID
    collection_id: UUID
    media_type: MediaType
    name: str
    description: str
    url: str | None
    metadata: JsonObject
    generation_source: str = 'upload'
    status: CollectionItemStatus = 'READY'
    generation_error_message: str | None = None
    job_id: UUID | None = None
    storage_provider: str | None = None
    storage_bucket: str | None = None
    storage_key: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class CollectionItemGenerationParams:
    prompt: str
    aspect_ratio: AspectRatio
    media_type: MediaType
    project_id: UUID
    collection_id: UUID
    reference_images: list[str] | None = None
    camera_setup: CameraSetup | None = None
    resolution: Resolution | None = None
    batch_size: BatchSize | None = None


@dataclass(frozen=True, slots=True)
class GeneratedCollectionItem:
    url: str
    thumbnail_url: str
    width: int
    height: int
    format: str
    duration: int | None = None
