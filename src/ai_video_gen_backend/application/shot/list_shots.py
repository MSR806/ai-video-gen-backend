from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.shot import Shot, ShotRepositoryPort


class ListShotsUseCase:
    def __init__(self, shot_repository: ShotRepositoryPort) -> None:
        self._shot_repository = shot_repository

    def execute(self, scene_id: UUID) -> list[Shot]:
        return self._shot_repository.list_shots(scene_id)
