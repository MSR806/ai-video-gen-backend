from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import Project, ProjectCreationPayload, ProjectUpdatePayload


class ProjectRepositoryPort(Protocol):
    def get_all_projects(self) -> list[Project]: ...

    def get_project_by_id(self, project_id: UUID) -> Project | None: ...

    def create_project(self, payload: ProjectCreationPayload) -> Project: ...

    def update_project(self, project_id: UUID, payload: ProjectUpdatePayload) -> Project | None: ...
