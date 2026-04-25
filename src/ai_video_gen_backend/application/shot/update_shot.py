from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.shot import Shot, ShotRepositoryPort, ShotUpdateInput


class UpdateShotUseCase:
    def __init__(self, shot_repository: ShotRepositoryPort) -> None:
        self._shot_repository = shot_repository

    def execute(self, scene_id: UUID, shot_id: UUID, payload: ShotUpdateInput) -> Shot | None:
        return self._shot_repository.update_shot(scene_id, shot_id, payload)
