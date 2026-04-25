from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_video_gen_backend.infrastructure.db.base import Base


class ShotModel(Base):
    __tablename__ = 'shots'
    __table_args__ = (
        sa.CheckConstraint('order_index > 0', name='ck_shots_order_index_positive'),
        sa.UniqueConstraint('scene_id', 'order_index', name='uq_shots_scene_order'),
        sa.Index('ix_shots_scene_id', 'scene_id'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    scene_id: Mapped[UUID] = mapped_column(
        Uuid,
        sa.ForeignKey('screenplay_scenes.id', ondelete='CASCADE'),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    camera_framing: Mapped[str] = mapped_column(String(255), nullable=False)
    camera_movement: Mapped[str] = mapped_column(String(255), nullable=False)
    mood: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    scene = relationship('ScreenplaySceneModel', back_populates='shots')
