from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.shot import Shot, ShotCreateInput, ShotRepositoryPort


class CreateShotUseCase:
    def __init__(self, shot_repository: ShotRepositoryPort) -> None:
        self._shot_repository = shot_repository

    def execute(self, scene_id: UUID, payload: ShotCreateInput) -> Shot | None:
        return self._shot_repository.create_shot(scene_id, payload)
