"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-01 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'projects',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('draft', 'in-progress', 'completed')", name='ck_projects_status'
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'collections',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('tag', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
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
        sa.UniqueConstraint('id', 'project_id', name='uq_collections_id_project_id'),
    )
    op.create_index('ix_collections_project_id', 'collections', ['project_id'], unique=False)

    op.create_table(
        'collection_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('collection_id', sa.Uuid(), nullable=False),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            'generation_source', sa.String(length=50), server_default='upload', nullable=False
        ),
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
        sa.CheckConstraint(
            "media_type IN ('image', 'video')", name='ck_collection_items_media_type'
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['collection_id', 'project_id'],
            ['collections.id', 'collections.project_id'],
            ondelete='CASCADE',
            name='fk_collection_items_collection_project',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_collection_items_collection_id', 'collection_items', ['collection_id'], unique=False
    )
    op.create_index(
        'ix_collection_items_project_id', 'collection_items', ['project_id'], unique=False
    )

    op.create_table(
        'scenes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('scene_number', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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


def downgrade() -> None:
    op.drop_index('ix_scenes_project_id', table_name='scenes')
    op.drop_table('scenes')

    op.drop_index('ix_collection_items_project_id', table_name='collection_items')
    op.drop_index('ix_collection_items_collection_id', table_name='collection_items')
    op.drop_table('collection_items')

    op.drop_index('ix_collections_project_id', table_name='collections')
    op.drop_table('collections')

    op.drop_table('projects')
