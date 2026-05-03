from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ai_video_gen_backend.application.project import (
    CreateProjectUseCase,
    GetAllProjectsUseCase,
    GetProjectByIdUseCase,
    UpdateProjectUseCase,
)
from ai_video_gen_backend.domain.project import (
    Project,
    ProjectCreationPayload,
    ProjectUpdatePayload,
)


class FakeProjectRepository:
    def __init__(self, projects: list[Project]) -> None:
        self.projects = projects

    def get_all_projects(self) -> list[Project]:
        return self.projects

    def get_project_by_id(self, project_id: UUID) -> Project | None:
        return next((project for project in self.projects if project.id == project_id), None)

    def create_project(self, payload: ProjectCreationPayload) -> Project:
        now = datetime.now(UTC)
        project = Project(
            id=uuid4(),
            name=payload.name,
            description=payload.description,
            style=payload.style,
            aspect_ratio=payload.aspect_ratio,
            status=payload.status,
            created_at=now,
            updated_at=now,
        )
        self.projects.append(project)
        return project

    def update_project(self, project_id: UUID, payload: ProjectUpdatePayload) -> Project | None:
        project = self.get_project_by_id(project_id)
        if project is None:
            return None

        now = datetime.now(UTC)
        updated = Project(
            id=project.id,
            name=payload.name if payload.update_name and payload.name is not None else project.name,
            description=(
                payload.description
                if payload.update_description and payload.description is not None
                else project.description
            ),
            style=payload.style if payload.update_style else project.style,
            aspect_ratio=(
                payload.aspect_ratio
                if payload.update_aspect_ratio and payload.aspect_ratio is not None
                else project.aspect_ratio
            ),
            status=project.status,
            created_at=project.created_at,
            updated_at=now,
        )
        self.projects = [
            updated if candidate.id == project_id else candidate for candidate in self.projects
        ]
        return updated


def _project_fixture(project_id: UUID) -> Project:
    now = datetime.now(UTC)
    return Project(
        id=project_id,
        name='Demo',
        description='Demo description',
        style=None,
        aspect_ratio='16:9',
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


def test_create_project_use_case_creates_new_project() -> None:
    repository = FakeProjectRepository([])
    use_case = CreateProjectUseCase(repository)

    result = use_case.execute(
        ProjectCreationPayload(
            name='New Project',
            description='Created in unit test',
            style='cinematic, moody',
            aspect_ratio='4:3',
            status='draft',
        )
    )

    assert result.name == 'New Project'
    assert result.description == 'Created in unit test'
    assert result.style == 'cinematic, moody'
    assert result.aspect_ratio == '4:3'
    assert result.status == 'draft'


def test_update_project_use_case_updates_only_requested_fields() -> None:
    project = _project_fixture(uuid4())
    repository = FakeProjectRepository([project])
    use_case = UpdateProjectUseCase(repository)

    result = use_case.execute(
        project.id,
        ProjectUpdatePayload(
            style='storybook watercolor',
            aspect_ratio='9:16',
            update_style=True,
            update_aspect_ratio=True,
        ),
    )

    assert result is not None
    assert result.id == project.id
    assert result.name == project.name
    assert result.description == project.description
    assert result.status == project.status
    assert result.style == 'storybook watercolor'
    assert result.aspect_ratio == '9:16'


def test_update_project_use_case_returns_none_when_missing_project() -> None:
    use_case = UpdateProjectUseCase(FakeProjectRepository([]))

    result = use_case.execute(
        uuid4(),
        ProjectUpdatePayload(name='Noop', update_name=True),
    )

    assert result is None
