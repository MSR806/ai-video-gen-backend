from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.scene import Scene, SceneCreateInput, SceneRepositoryPort


class CreateSceneUseCase:
    def __init__(self, scene_repository: SceneRepositoryPort) -> None:
        self._scene_repository = scene_repository

    def execute(self, project_id: UUID, payload: SceneCreateInput) -> list[Scene]:
        return self._scene_repository.create_scene(project_id, payload)
