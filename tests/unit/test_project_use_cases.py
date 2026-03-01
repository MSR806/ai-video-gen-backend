from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ai_video_gen_backend.application.project import GetAllProjectsUseCase, GetProjectByIdUseCase
from ai_video_gen_backend.domain.project import Project


class FakeProjectRepository:
    def __init__(self, projects: list[Project]) -> None:
        self.projects = projects

    def get_all_projects(self) -> list[Project]:
        return self.projects

    def get_project_by_id(self, project_id: UUID) -> Project | None:
        return next((project for project in self.projects if project.id == project_id), None)


def _project_fixture(project_id: UUID) -> Project:
    now = datetime.now(UTC)
    return Project(
        id=project_id,
        name='Demo',
        description='Demo description',
        status='draft',
        created_at=now,
        updated_at=now,
    )


def test_get_all_projects_use_case_returns_all_projects() -> None:
    project = _project_fixture(uuid4())
    use_case = GetAllProjectsUseCase(FakeProjectRepository([project]))

    result = use_case.execute()

    assert result == [project]


def test_get_project_by_id_use_case_returns_matching_project() -> None:
    project = _project_fixture(uuid4())
    use_case = GetProjectByIdUseCase(FakeProjectRepository([project]))

    result = use_case.execute(project.id)

    assert result == project
