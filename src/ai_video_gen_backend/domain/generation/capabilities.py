from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_video_gen_backend.domain.types import JsonObject, JsonValue

ModelMediaType = Literal['image', 'video']
MediaGroupLayout = Literal['single', 'sequence', 'gallery']
MediaGroupPlacement = Literal['top']


@dataclass(frozen=True, slots=True)
class MediaGroupCapability:
    group_key: str
    layout: MediaGroupLayout
    placement: MediaGroupPlacement


@dataclass(frozen=True, slots=True)
class InputFieldCapability:
    key: str
    type: str
    required: bool
    ui_group: str | None
    title: str | None
    description: str | None
    default: JsonValue | None
    enum: list[JsonValue] | None
    format: str | None
    items_type: str | None
    minimum: JsonValue | None
    maximum: JsonValue | None
    media_group: str | None
    media_order: int | None
    media_name: str | None


@dataclass(frozen=True, slots=True)
class OperationCapability:
    operation_key: str
    operation_type: str
    operation_name: str
    endpoint_id: str
    required: list[str]
    input_schema: JsonObject
    fields: list[InputFieldCapability]
    media_groups: list[MediaGroupCapability]


@dataclass(frozen=True, slots=True)
class ModelCapability:
    model: str
    model_key: str
    provider: str
    media_type: ModelMediaType
    operations: list[OperationCapability]


@dataclass(frozen=True, slots=True)
class GenerationCapabilities:
    image: list[ModelCapability]
    video: list[ModelCapability]


@dataclass(frozen=True, slots=True)
class ResolvedGenerationOperation:
    model_key: str
    model_display_name: str
    provider: str
    media_type: ModelMediaType
    operation_key: str
    operation_type: str
    operation_name: str
    endpoint_id: str
    input_schema: JsonObject
