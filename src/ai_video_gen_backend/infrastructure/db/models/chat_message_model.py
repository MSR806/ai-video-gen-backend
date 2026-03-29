from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_video_gen_backend.domain.types import JsonValue
from ai_video_gen_backend.infrastructure.db.base import Base
from ai_video_gen_backend.infrastructure.db.types import JSONType


class ChatMessageModel(Base):
    __tablename__ = 'chat_messages'
    __table_args__ = (
        sa.CheckConstraint("role IN ('user', 'assistant')", name='ck_chat_messages_role'),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
        sa.Index('ix_chat_messages_thread_id', 'thread_id'),
        sa.Index('ix_chat_messages_thread_created_at', 'thread_id', 'created_at'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    thread_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    images_json: Mapped[list[JsonValue]] = mapped_column(JSONType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    thread = relationship('ChatThreadModel', back_populates='messages')
