"""add project style/aspect ratio and shot collection reference

Revision ID: 0016_project_aspect_ratio_and_shot_collection
Revises: 0015_shots_mvp
Create Date: 2026-05-03 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0016_project_aspect_ratio_and_shot_collection'
down_revision = '0015_shots_mvp'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('style', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('aspect_ratio', sa.String(length=20), nullable=True))

    op.add_column('shots', sa.Column('collection_id', sa.Uuid(), nullable=True))
    op.create_index('ix_shots_collection_id', 'shots', ['collection_id'], unique=False)
    op.create_foreign_key(
        'fk_shots_collection_id_collections',
        'shots',
        'collections',
        ['collection_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_shots_collection_id_collections', 'shots', type_='foreignkey')
    op.drop_index('ix_shots_collection_id', table_name='shots')
    op.drop_column('shots', 'collection_id')

    op.drop_column('projects', 'aspect_ratio')
    op.drop_column('projects', 'style')
