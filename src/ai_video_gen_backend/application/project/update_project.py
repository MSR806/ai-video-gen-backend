from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.project import Project, ProjectRepositoryPort, ProjectUpdatePayload


class UpdateProjectUseCase:
    def __init__(self, project_repository: ProjectRepositoryPort) -> None:
        self._project_repository = project_repository

    def execute(self, project_id: UUID, payload: ProjectUpdatePayload) -> Project | None:
        return self._project_repository.update_project(project_id, payload)
