"""collection hierarchy

Revision ID: 0006_collection_hierarchy
Revises: 0005_collection_item_job_id
Create Date: 2026-03-04 19:45:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0006_collection_hierarchy'
down_revision = '0005_collection_item_job_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('collections', sa.Column('parent_collection_id', sa.Uuid(), nullable=True))
    op.create_check_constraint(
        'ck_collections_parent_not_self',
        'collections',
        'parent_collection_id IS NULL OR parent_collection_id <> id',
    )
    op.create_foreign_key(
        'fk_collections_parent_project',
        'collections',
        'collections',
        ['parent_collection_id', 'project_id'],
        ['id', 'project_id'],
    )
    op.create_index(
        'ix_collections_parent_collection_id',
        'collections',
        ['parent_collection_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_collections_parent_collection_id', table_name='collections')
    op.drop_constraint('fk_collections_parent_project', 'collections', type_='foreignkey')
    op.drop_constraint('ck_collections_parent_not_self', 'collections', type_='check')
    op.drop_column('collections', 'parent_collection_id')
