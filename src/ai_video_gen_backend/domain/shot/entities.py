from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Shot:
    id: UUID
    scene_id: UUID
    collection_id: UUID | None
    order_index: int
    title: str
    description: str
    camera_framing: str
    camera_movement: str
    mood: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ShotCreateInput:
    title: str
    description: str
    camera_framing: str
    camera_movement: str
    mood: str


@dataclass(frozen=True, slots=True)
class ShotUpdateInput:
    title: str | None = None
    description: str | None = None
    camera_framing: str | None = None
    camera_movement: str | None = None
    mood: str | None = None


@dataclass(frozen=True, slots=True)
class ShotReorderInput:
    shot_ids: list[UUID]


@dataclass(frozen=True, slots=True)
class ShotImagePromptCraftRequest:
    project_name: str
    project_style: str | None
    shot_title: str
    shot_description: str
    camera_framing: str
    camera_movement: str
    mood: str
    scene_context: str


@dataclass(frozen=True, slots=True)
class ShotImagePromptCraftResult:
    prompt: str
