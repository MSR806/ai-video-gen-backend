from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import Scene, SceneCreateInput, SceneUpdateInput


class SceneRepositoryPort(Protocol):
    def get_scenes_by_project_id(self, project_id: UUID) -> list[Scene]: ...

    def get_scene_by_id(self, scene_id: UUID) -> Scene | None: ...

    def create_scene(self, project_id: UUID, payload: SceneCreateInput) -> list[Scene]: ...

    def update_scene(
        self,
        project_id: UUID,
        scene_id: UUID,
        payload: SceneUpdateInput,
    ) -> Scene | None: ...

    def delete_scene(self, project_id: UUID, scene_id: UUID) -> list[Scene] | None: ...
