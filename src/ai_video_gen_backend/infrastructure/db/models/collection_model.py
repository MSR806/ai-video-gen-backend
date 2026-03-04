from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_video_gen_backend.infrastructure.db.base import Base


class CollectionModel(Base):
    __tablename__ = 'collections'
    __table_args__ = (
        sa.UniqueConstraint('id', 'project_id', name='uq_collections_id_project_id'),
        sa.CheckConstraint(
            'parent_collection_id IS NULL OR parent_collection_id <> id',
            name='ck_collections_parent_not_self',
        ),
        sa.ForeignKeyConstraint(
            ['parent_collection_id', 'project_id'],
            ['collections.id', 'collections.project_id'],
            name='fk_collections_parent_project',
        ),
        sa.Index('ix_collections_project_id', 'project_id'),
        sa.Index('ix_collections_parent_collection_id', 'parent_collection_id'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        sa.ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
    )
    parent_collection_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tag: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project = relationship('ProjectModel', back_populates='collections')
    parent = relationship(
        'CollectionModel',
        back_populates='children',
        remote_side='CollectionModel.id',
        foreign_keys=[parent_collection_id],
    )
    children = relationship(
        'CollectionModel',
        back_populates='parent',
        foreign_keys=[parent_collection_id],
    )
    items = relationship(
        'CollectionItemModel', back_populates='collection', cascade='all, delete-orphan'
    )
