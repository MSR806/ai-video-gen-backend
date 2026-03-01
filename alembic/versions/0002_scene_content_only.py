"""scene content only

Revision ID: 0002_scene_content_only
Revises: 0001_initial_schema
Create Date: 2026-03-01 15:35:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002_scene_content_only'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'scenes',
        'content',
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
    )
    op.drop_column('scenes', 'body')


def downgrade() -> None:
    op.add_column(
        'scenes',
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
    )
    op.execute(
        """
        UPDATE scenes
        SET body = COALESCE(content->>'text', '')
        """
    )
    op.alter_column(
        'scenes',
        'body',
        existing_type=sa.Text(),
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        'scenes',
        'content',
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
    )
