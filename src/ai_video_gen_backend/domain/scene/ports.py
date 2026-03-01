from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import Scene


class SceneRepositoryPort(Protocol):
    def get_scenes_by_project_id(self, project_id: UUID) -> list[Scene]: ...

    def get_scene_by_id(self, scene_id: UUID) -> Scene | None: ...

    def bulk_replace(self, project_id: UUID, scenes: list[Scene]) -> None: ...
