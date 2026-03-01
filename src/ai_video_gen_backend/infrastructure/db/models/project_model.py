from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_video_gen_backend.domain.project import ProjectStatus
from ai_video_gen_backend.infrastructure.db.base import Base


class ProjectModel(Base):
    __tablename__ = 'projects'
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('draft', 'in-progress', 'completed')",
            name='ck_projects_status',
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    collections = relationship(
        'CollectionModel',
        back_populates='project',
        cascade='all, delete-orphan',
    )
    scenes = relationship('SceneModel', back_populates='project', cascade='all, delete-orphan')
