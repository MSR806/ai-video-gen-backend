from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.screenplay import Screenplay, ScreenplayRepositoryPort


class UpdateScreenplayTitleUseCase:
    def __init__(self, screenplay_repository: ScreenplayRepositoryPort) -> None:
        self._screenplay_repository = screenplay_repository

    def execute(self, screenplay_id: UUID, title: str) -> Screenplay | None:
        return self._screenplay_repository.update_screenplay_title(screenplay_id, title)
