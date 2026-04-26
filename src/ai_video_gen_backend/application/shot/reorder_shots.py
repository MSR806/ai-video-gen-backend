from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.shot import Shot, ShotRepositoryPort


class ReorderShotsUseCase:
    def __init__(self, shot_repository: ShotRepositoryPort) -> None:
        self._shot_repository = shot_repository

    def execute(self, scene_id: UUID, shot_ids: list[UUID]) -> list[Shot] | None:
        return self._shot_repository.reorder_shots(scene_id, shot_ids)
