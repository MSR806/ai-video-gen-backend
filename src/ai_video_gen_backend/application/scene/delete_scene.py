from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.scene import Scene, SceneRepositoryPort


class DeleteSceneUseCase:
    def __init__(self, scene_repository: SceneRepositoryPort) -> None:
        self._scene_repository = scene_repository

    def execute(self, project_id: UUID, scene_id: UUID) -> list[Scene] | None:
        return self._scene_repository.delete_scene(project_id, scene_id)
