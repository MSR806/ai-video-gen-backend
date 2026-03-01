"""collection item storage fields

Revision ID: 0003_item_storage_fields
Revises: 0002_scene_content_only
Create Date: 2026-03-01 18:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0003_item_storage_fields'
down_revision = '0002_scene_content_only'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'collection_items',
        sa.Column('storage_provider', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'collection_items',
        sa.Column('storage_bucket', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'collection_items',
        sa.Column('storage_key', sa.Text(), nullable=True),
    )
    op.add_column(
        'collection_items',
        sa.Column('mime_type', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'collection_items',
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
    )
    op.create_index(
        'ix_collection_items_storage_bucket_key',
        'collection_items',
        ['storage_bucket', 'storage_key'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_collection_items_storage_bucket_key', table_name='collection_items')
    op.drop_column('collection_items', 'size_bytes')
    op.drop_column('collection_items', 'mime_type')
    op.drop_column('collection_items', 'storage_key')
    op.drop_column('collection_items', 'storage_bucket')
    op.drop_column('collection_items', 'storage_provider')
