from __future__ import annotations

from ai_video_gen_backend.domain.project import Project, ProjectRepositoryPort


class GetAllProjectsUseCase:
    def __init__(self, project_repository: ProjectRepositoryPort) -> None:
        self._project_repository = project_repository

    def execute(self) -> list[Project]:
        return self._project_repository.get_all_projects()
