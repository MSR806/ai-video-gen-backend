"""screenplay foundation tables

Revision ID: 0012_screenplay_foundation
Revises: 0011_chat_threads_messages
Create Date: 2026-04-04 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0012_screenplay_foundation'
down_revision = '0011_chat_threads_messages'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'screenplays',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
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
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_screenplays_project_id'),
    )
    op.create_index('ix_screenplays_project_id', 'screenplays', ['project_id'], unique=False)

    op.create_table(
        'screenplay_scenes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('screenplay_id', sa.Uuid(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('content_json', sa.JSON(), nullable=False),
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
        sa.CheckConstraint('order_index > 0', name='ck_screenplay_scenes_order_index_positive'),
        sa.ForeignKeyConstraint(['screenplay_id'], ['screenplays.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'screenplay_id',
            'order_index',
            name='uq_screenplay_scenes_screenplay_order',
        ),
    )
    op.create_index(
        'ix_screenplay_scenes_screenplay_id',
        'screenplay_scenes',
        ['screenplay_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_screenplay_scenes_screenplay_id', table_name='screenplay_scenes')
    op.drop_table('screenplay_scenes')
    op.drop_index('ix_screenplays_project_id', table_name='screenplays')
    op.drop_table('screenplays')
