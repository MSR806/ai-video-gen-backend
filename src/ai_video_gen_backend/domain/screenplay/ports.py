from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import (
    Screenplay,
    ScreenplayCreateInput,
    ScreenplayScene,
    ScreenplaySceneCreateInput,
    ScreenplaySceneUpdateInput,
)


class ScreenplayRepositoryPort(Protocol):
    def get_screenplay_by_project_id(self, project_id: UUID) -> Screenplay | None: ...

    def create_screenplay(self, project_id: UUID, payload: ScreenplayCreateInput) -> Screenplay: ...

    def update_screenplay_title(self, screenplay_id: UUID, title: str) -> Screenplay | None: ...

    def create_screenplay_scene(
        self,
        screenplay_id: UUID,
        payload: ScreenplaySceneCreateInput,
    ) -> Screenplay | None: ...

    def update_screenplay_scene(
        self,
        screenplay_id: UUID,
        scene_id: UUID,
        payload: ScreenplaySceneUpdateInput,
    ) -> ScreenplayScene | None: ...

    def delete_screenplay_scene(self, screenplay_id: UUID, scene_id: UUID) -> Screenplay | None: ...

    def reorder_screenplay_scenes(
        self, screenplay_id: UUID, scene_ids: list[UUID]
    ) -> Screenplay | None: ...
