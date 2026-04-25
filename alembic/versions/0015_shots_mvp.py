"""add manual scene-linked shots

Revision ID: 0015_shots_mvp
Revises: 0014_screenplay_xml_content
Create Date: 2026-04-25 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0015_shots_mvp'
down_revision = '0014_screenplay_xml_content'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'shots',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('scene_id', sa.Uuid(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('camera_framing', sa.String(length=255), nullable=False),
        sa.Column('camera_movement', sa.String(length=255), nullable=False),
        sa.Column('mood', sa.String(length=255), nullable=False),
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
        sa.CheckConstraint('order_index > 0', name='ck_shots_order_index_positive'),
        sa.ForeignKeyConstraint(['scene_id'], ['screenplay_scenes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scene_id', 'order_index', name='uq_shots_scene_order'),
    )
    op.create_index('ix_shots_scene_id', 'shots', ['scene_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_shots_scene_id', table_name='shots')
    op.drop_table('shots')
