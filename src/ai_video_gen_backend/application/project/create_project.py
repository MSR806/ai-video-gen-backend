from __future__ import annotations

from ai_video_gen_backend.domain.project import (
    Project,
    ProjectCreationPayload,
    ProjectRepositoryPort,
)


class CreateProjectUseCase:
    def __init__(self, project_repository: ProjectRepositoryPort) -> None:
        self._project_repository = project_repository

    def execute(self, payload: ProjectCreationPayload) -> Project:
        return self._project_repository.create_project(payload)
