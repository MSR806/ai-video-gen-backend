from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.screenplay import Screenplay, ScreenplayRepositoryPort


class ReorderScreenplayScenesUseCase:
    def __init__(self, screenplay_repository: ScreenplayRepositoryPort) -> None:
        self._screenplay_repository = screenplay_repository

    def execute(self, screenplay_id: UUID, scene_ids: list[UUID]) -> Screenplay | None:
        return self._screenplay_repository.reorder_screenplay_scenes(screenplay_id, scene_ids)
