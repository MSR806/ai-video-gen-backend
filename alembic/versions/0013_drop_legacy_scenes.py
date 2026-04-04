"""drop legacy scenes table

Revision ID: 0013_drop_legacy_scenes
Revises: 0012_screenplay_foundation
Create Date: 2026-04-04 00:00:01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0013_drop_legacy_scenes'
down_revision = '0012_screenplay_foundation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index('ix_scenes_project_id', table_name='scenes')
    op.drop_table('scenes')


def downgrade() -> None:
    op.create_table(
        'scenes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('scene_number', sa.Integer(), nullable=False),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint('scene_number > 0', name='ck_scenes_scene_number_positive'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'scene_number', name='uq_scenes_project_scene_number'),
    )
    op.create_index('ix_scenes_project_id', 'scenes', ['project_id'], unique=False)
