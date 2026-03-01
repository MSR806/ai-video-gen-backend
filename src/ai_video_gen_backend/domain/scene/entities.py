from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

JsonValue = object
JsonObject = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Scene:
    id: UUID
    project_id: UUID
    name: str
    scene_number: int
    body: str
    content: JsonObject | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SceneInput:
    id: UUID | None = None
    name: str | None = None
    scene_number: int | None = None
    body: str | None = None
    content: JsonObject | None = None
