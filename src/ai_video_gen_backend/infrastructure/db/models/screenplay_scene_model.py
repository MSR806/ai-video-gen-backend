from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_video_gen_backend.infrastructure.db.base import Base


class ScreenplaySceneModel(Base):
    __tablename__ = 'screenplay_scenes'
    __table_args__ = (
        sa.CheckConstraint('order_index > 0', name='ck_screenplay_scenes_order_index_positive'),
        sa.UniqueConstraint(
            'screenplay_id',
            'order_index',
            name='uq_screenplay_scenes_screenplay_order',
        ),
        sa.Index('ix_screenplay_scenes_screenplay_id', 'screenplay_id'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    screenplay_id: Mapped[UUID] = mapped_column(
        Uuid,
        sa.ForeignKey('screenplays.id', ondelete='CASCADE'),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_xml: Mapped[str] = mapped_column('content_xml', Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    screenplay = relationship('ScreenplayModel', back_populates='scenes')
