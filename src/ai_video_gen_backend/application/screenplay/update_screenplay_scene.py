from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.screenplay import (
    ScreenplayRepositoryPort,
    ScreenplayScene,
    ScreenplaySceneUpdateInput,
)


class UpdateScreenplaySceneUseCase:
    def __init__(self, screenplay_repository: ScreenplayRepositoryPort) -> None:
        self._screenplay_repository = screenplay_repository

    def execute(
        self,
        screenplay_id: UUID,
        scene_id: UUID,
        payload: ScreenplaySceneUpdateInput,
    ) -> ScreenplayScene | None:
        return self._screenplay_repository.update_screenplay_scene(screenplay_id, scene_id, payload)
