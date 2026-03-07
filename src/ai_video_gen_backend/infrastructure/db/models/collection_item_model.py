from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, String, Uuid, func
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
        sa.CheckConstraint(
            "status IN ('GENERATING', 'READY', 'FAILED')", name='ck_collection_items_status'
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['collection_id', 'project_id'],
            ['collections.id', 'collections.project_id'],
            ondelete='CASCADE',
            name='fk_collection_items_collection_project',
        ),
        sa.ForeignKeyConstraint(
            ['run_id'],
            ['generation_runs.id'],
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['generation_run_output_id'],
            ['generation_run_outputs.id'],
            ondelete='SET NULL',
        ),
        sa.Index('ix_collection_items_collection_id', 'collection_id'),
        sa.Index('ix_collection_items_project_id', 'project_id'),
        sa.Index('ix_collection_items_run_id', 'run_id'),
        sa.Index('ix_collection_items_generation_run_output_id', 'generation_run_output_id'),
        sa.Index(
            'uq_collection_items_generation_run_output_id',
            'generation_run_output_id',
            unique=True,
            postgresql_where=sa.text('generation_run_output_id IS NOT NULL'),
            sqlite_where=sa.text('generation_run_output_id IS NOT NULL'),
        ),
        sa.Index('ix_collection_items_storage_bucket_key', 'storage_bucket', 'storage_key'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    collection_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    media_type: Mapped[MediaType] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    metadata_json: Mapped[dict[str, JsonValue]] = mapped_column(
        'metadata', JSONType, nullable=False
    )
    generation_source: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default='upload'
    )
    run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    generation_run_output_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='READY',
        server_default='READY',
    )
    generation_error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    storage_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    collection = relationship('CollectionModel', back_populates='items')
