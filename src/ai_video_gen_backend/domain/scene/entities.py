from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ai_video_gen_backend.domain.types import JsonObject, JsonValue

__all__ = ['JsonObject', 'JsonValue']


@dataclass(frozen=True, slots=True)
class Scene:
    id: UUID
    project_id: UUID
    name: str
    scene_number: int
    content: JsonObject
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SceneCreateInput:
    id: UUID | None = None
    position: int | None = None
    name: str | None = None
    content: JsonObject | None = None


@dataclass(frozen=True, slots=True)
class SceneUpdateInput:
    name: str | None = None
    content: JsonObject | None = None
    update_name: bool = False
    update_content: bool = False
