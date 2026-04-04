from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from ai_video_gen_backend.domain.types import JsonValue

ScreenplayBlockType = Literal[
    'slugline',
    'action',
    'character',
    'parenthetical',
    'dialogue',
    'transition',
]


@dataclass(frozen=True, slots=True)
class ScreenplayBlock:
    id: str
    type: ScreenplayBlockType
    text: str


@dataclass(frozen=True, slots=True)
class ScreenplayScene:
    id: UUID
    screenplay_id: UUID
    order_index: int
    content: list[JsonValue]
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
    content: list[JsonValue]


@dataclass(frozen=True, slots=True)
class ScreenplaySceneUpdateInput:
    content: list[JsonValue]


@dataclass(frozen=True, slots=True)
class ScreenplayReorderScenesInput:
    scene_ids: list[UUID]
