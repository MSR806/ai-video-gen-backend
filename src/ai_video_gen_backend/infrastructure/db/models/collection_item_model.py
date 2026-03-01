from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_video_gen_backend.domain.collection_item import JsonValue, MediaType
from ai_video_gen_backend.infrastructure.db.base import Base
from ai_video_gen_backend.infrastructure.db.types import JSONType


class CollectionItemModel(Base):
    __tablename__ = 'collection_items'
    __table_args__ = (
        sa.CheckConstraint(
            "media_type IN ('image', 'video')", name='ck_collection_items_media_type'
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['collection_id', 'project_id'],
            ['collections.id', 'collections.project_id'],
            ondelete='CASCADE',
            name='fk_collection_items_collection_project',
        ),
        sa.Index('ix_collection_items_collection_id', 'collection_id'),
        sa.Index('ix_collection_items_project_id', 'project_id'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    collection_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    media_type: Mapped[MediaType] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    metadata_json: Mapped[dict[str, JsonValue]] = mapped_column(
        'metadata', JSONType, nullable=False
    )
    generation_source: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default='upload'
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    collection = relationship('CollectionModel', back_populates='items')
