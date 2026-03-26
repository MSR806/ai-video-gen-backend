"""add collection item favorite flag

Revision ID: 0010_collection_item_favorite
Revises: 0009_drop_generation_jobs
Create Date: 2026-03-26 14:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0010_collection_item_favorite'
down_revision = '0009_drop_generation_jobs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'collection_items',
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('collection_items', 'is_favorite')
