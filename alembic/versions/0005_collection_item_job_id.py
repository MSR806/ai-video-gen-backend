"""add collection item job id

Revision ID: 0005_collection_item_job_id
Revises: 4fe5f5908953
Create Date: 2026-03-03 13:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0005_collection_item_job_id'
down_revision = '4fe5f5908953'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('collection_items', sa.Column('job_id', sa.Uuid(), nullable=True))
    op.create_index('ix_collection_items_job_id', 'collection_items', ['job_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_collection_items_job_id', table_name='collection_items')
    op.drop_column('collection_items', 'job_id')
