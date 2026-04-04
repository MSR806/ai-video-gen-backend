from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.screenplay import Screenplay, ScreenplayRepositoryPort


class GetProjectScreenplayUseCase:
    def __init__(self, screenplay_repository: ScreenplayRepositoryPort) -> None:
        self._screenplay_repository = screenplay_repository

    def execute(self, project_id: UUID) -> Screenplay | None:
        return self._screenplay_repository.get_screenplay_by_project_id(project_id)
