from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_video_gen_backend.domain.types import JsonObject, JsonValue

ModelMediaType = Literal['image', 'video']


@dataclass(frozen=True, slots=True)
class InputFieldCapability:
    key: str
    type: str
    required: bool
    description: str | None
    default: JsonValue | None
    enum: list[JsonValue] | None
    format: str | None
    items_type: str | None


@dataclass(frozen=True, slots=True)
class OperationCapability:
    operation_key: str
    endpoint_id: str
    required: list[str]
    input_schema: JsonObject
    fields: list[InputFieldCapability]


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
    endpoint_id: str
    input_schema: JsonObject
