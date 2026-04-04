from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.screenplay import (
    Screenplay,
    ScreenplayCreateInput,
    ScreenplayRepositoryPort,
)


class CreateScreenplayUseCase:
    def __init__(self, screenplay_repository: ScreenplayRepositoryPort) -> None:
        self._screenplay_repository = screenplay_repository

    def execute(self, project_id: UUID, payload: ScreenplayCreateInput) -> Screenplay:
        return self._screenplay_repository.create_screenplay(project_id, payload)
