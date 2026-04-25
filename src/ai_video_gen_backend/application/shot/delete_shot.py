from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.shot import ShotRepositoryPort


class DeleteShotUseCase:
    def __init__(self, shot_repository: ShotRepositoryPort) -> None:
        self._shot_repository = shot_repository

    def execute(self, scene_id: UUID, shot_id: UUID) -> bool:
        return self._shot_repository.delete_shot(scene_id, shot_id)
