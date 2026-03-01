from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.scene import Scene, SceneRepositoryPort


class GetProjectScenesUseCase:
    def __init__(self, scene_repository: SceneRepositoryPort) -> None:
        self._scene_repository = scene_repository

    def execute(self, project_id: UUID) -> list[Scene]:
        return self._scene_repository.get_scenes_by_project_id(project_id)
