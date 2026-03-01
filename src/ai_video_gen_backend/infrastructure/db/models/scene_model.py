from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_video_gen_backend.domain.scene.entities import JsonValue
from ai_video_gen_backend.infrastructure.db.base import Base
from ai_video_gen_backend.infrastructure.db.types import JSONType


class SceneModel(Base):
    __tablename__ = 'scenes'
    __table_args__ = (
        sa.CheckConstraint('scene_number > 0', name='ck_scenes_scene_number_positive'),
        sa.UniqueConstraint('project_id', 'scene_number', name='uq_scenes_project_scene_number'),
        sa.Index('ix_scenes_project_id', 'project_id'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        sa.ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict[str, JsonValue]] = mapped_column('content', JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project = relationship('ProjectModel', back_populates='scenes')
