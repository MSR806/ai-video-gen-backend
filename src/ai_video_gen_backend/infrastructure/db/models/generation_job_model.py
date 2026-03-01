from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ai_video_gen_backend.domain.collection_item import JsonValue
from ai_video_gen_backend.infrastructure.db.base import Base
from ai_video_gen_backend.infrastructure.db.types import JSONType


class GenerationJobModel(Base):
    __tablename__ = 'generation_jobs'
    __table_args__ = (
        sa.CheckConstraint(
            "operation IN ('TEXT_TO_IMAGE', 'IMAGE_TO_IMAGE')",
            name='ck_generation_jobs_operation',
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name='ck_generation_jobs_status',
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['collection_item_id'],
            ['collection_items.id'],
            ondelete='SET NULL',
        ),
        sa.Index('ix_generation_jobs_project_id', 'project_id'),
        sa.Index('ix_generation_jobs_collection_id', 'collection_id'),
        sa.Index('ix_generation_jobs_status', 'status'),
        sa.Index(
            'uq_generation_jobs_provider_request_id',
            'provider_request_id',
            unique=True,
            postgresql_where=sa.text('provider_request_id IS NOT NULL'),
            sqlite_where=sa.text('provider_request_id IS NOT NULL'),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    collection_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    collection_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    request_payload: Mapped[dict[str, JsonValue]] = mapped_column(JSONType, nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_response: Mapped[dict[str, JsonValue] | None] = mapped_column(JSONType, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
