from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import Project


class ProjectRepositoryPort(Protocol):
    def get_all_projects(self) -> list[Project]: ...

    def get_project_by_id(self, project_id: UUID) -> Project | None: ...
