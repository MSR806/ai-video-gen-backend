from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_video_gen_backend.infrastructure.db.base import Base


class ChatThreadModel(Base):
    __tablename__ = 'chat_threads'

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages = relationship(
        'ChatMessageModel', back_populates='thread', cascade='all, delete-orphan'
    )
