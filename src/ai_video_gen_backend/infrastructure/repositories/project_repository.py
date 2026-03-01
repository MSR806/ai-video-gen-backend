from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.project import Project, ProjectCreationPayload
from ai_video_gen_backend.infrastructure.db.models import ProjectModel


class ProjectSqlRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all_projects(self) -> list[Project]:
        stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc())
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(record) for record in records]

    def get_project_by_id(self, project_id: UUID) -> Project | None:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        record = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(record) if record is not None else None

    def create_project(self, payload: ProjectCreationPayload) -> Project:
        model = ProjectModel(
            name=payload.name,
            description=payload.description,
            status=payload.status,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def _to_domain(self, model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            name=model.name,
            description=model.description,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
