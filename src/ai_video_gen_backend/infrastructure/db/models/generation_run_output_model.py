from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ai_video_gen_backend.domain.collection_item import JsonValue
from ai_video_gen_backend.infrastructure.db.base import Base
from ai_video_gen_backend.infrastructure.db.types import JSONType


class GenerationRunOutputModel(Base):
    __tablename__ = 'generation_run_outputs'
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('QUEUED', 'READY', 'FAILED')",
            name='ck_generation_run_outputs_status',
        ),
        sa.CheckConstraint(
            'output_index >= 0',
            name='ck_generation_run_outputs_output_index_non_negative',
        ),
        sa.ForeignKeyConstraint(
            ['run_id'],
            ['generation_runs.id'],
            ondelete='CASCADE',
        ),
        sa.UniqueConstraint(
            'run_id',
            'output_index',
            name='uq_generation_run_outputs_run_id_output_index',
        ),
        sa.Index('ix_generation_run_outputs_run_id', 'run_id'),
        sa.Index('ix_generation_run_outputs_status', 'status'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    output_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_output_json: Mapped[dict[str, JsonValue] | None] = mapped_column(
        JSONType,
        nullable=True,
    )
    stored_output_json: Mapped[dict[str, JsonValue] | None] = mapped_column(
        JSONType,
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
