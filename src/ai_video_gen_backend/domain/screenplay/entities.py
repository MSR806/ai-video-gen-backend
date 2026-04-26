from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ScreenplayScene:
    id: UUID
    screenplay_id: UUID
    order_index: int
    content: str
    shot_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Screenplay:
    id: UUID
    project_id: UUID
    title: str
    scenes: list[ScreenplayScene]
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ScreenplayCreateInput:
    title: str


@dataclass(frozen=True, slots=True)
class ScreenplaySceneCreateInput:
    position: int | None
    content: str


@dataclass(frozen=True, slots=True)
class ScreenplaySceneUpdateInput:
    content: str


@dataclass(frozen=True, slots=True)
class ScreenplayReorderScenesInput:
    scene_ids: list[UUID]
