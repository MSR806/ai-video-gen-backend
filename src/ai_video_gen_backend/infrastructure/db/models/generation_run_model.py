from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ai_video_gen_backend.domain.collection_item import JsonValue
from ai_video_gen_backend.infrastructure.db.base import Base
from ai_video_gen_backend.infrastructure.db.types import JSONType


class GenerationRunModel(Base):
    __tablename__ = 'generation_runs'
    __table_args__ = (
        sa.CheckConstraint(
            (
                'status IN '
                "('QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'PARTIAL_FAILED', 'FAILED', 'CANCELLED')"
            ),
            name='ck_generation_runs_status',
        ),
        sa.CheckConstraint(
            'requested_output_count > 0',
            name='ck_generation_runs_requested_output_count_positive',
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.Index('ix_generation_runs_project_id', 'project_id'),
        sa.Index('ix_generation_runs_status', 'status'),
        sa.Index('ix_generation_runs_status_updated_at', 'status', sa.desc('updated_at')),
        sa.Index(
            'uq_generation_runs_provider_request_id',
            'provider_request_id',
            unique=True,
            postgresql_where=sa.text('provider_request_id IS NOT NULL'),
            sqlite_where=sa.text('provider_request_id IS NOT NULL'),
        ),
        sa.Index(
            'uq_generation_runs_idempotency',
            'project_id',
            'idempotency_key',
            unique=True,
            postgresql_where=sa.text('idempotency_key IS NOT NULL'),
            sqlite_where=sa.text('idempotency_key IS NOT NULL'),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_key: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_output_count: Mapped[int] = mapped_column(Integer, nullable=False)
    inputs_json: Mapped[dict[str, JsonValue]] = mapped_column(JSONType, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_response_json: Mapped[dict[str, JsonValue] | None] = mapped_column(
        JSONType, nullable=True
    )
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
