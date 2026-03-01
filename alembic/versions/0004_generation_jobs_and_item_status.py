"""generation jobs and collection item status

Revision ID: 0004_generation_jobs_and_item_status
Revises: 0003_item_storage_fields
Create Date: 2026-03-01 21:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0004_generation_jobs_and_item_status'
down_revision = '0003_item_storage_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'collection_items',
        sa.Column('status', sa.String(length=20), nullable=True, server_default='READY'),
    )
    op.add_column(
        'collection_items',
        sa.Column('generation_error_message', sa.Text(), nullable=True),
    )

    op.alter_column(
        'collection_items',
        'status',
        existing_type=sa.String(length=20),
        nullable=False,
        server_default='READY',
    )
    op.alter_column(
        'collection_items',
        'url',
        existing_type=sa.Text(),
        nullable=True,
    )
    op.create_check_constraint(
        'ck_collection_items_status',
        'collection_items',
        "status IN ('GENERATING', 'READY', 'FAILED')",
    )

    op.create_table(
        'generation_jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('collection_id', sa.Uuid(), nullable=False),
        sa.Column('collection_item_id', sa.Uuid(), nullable=True),
        sa.Column('operation', sa.String(length=32), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('model_key', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('request_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('provider_request_id', sa.String(length=255), nullable=True),
        sa.Column('provider_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
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
            "operation IN ('TEXT_TO_IMAGE', 'IMAGE_TO_IMAGE')",
            name='ck_generation_jobs_operation',
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name='ck_generation_jobs_status',
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['collection_item_id'], ['collection_items.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_generation_jobs_project_id',
        'generation_jobs',
        ['project_id'],
        unique=False,
    )
    op.create_index(
        'ix_generation_jobs_collection_id',
        'generation_jobs',
        ['collection_id'],
        unique=False,
    )
    op.create_index('ix_generation_jobs_status', 'generation_jobs', ['status'], unique=False)
    op.create_index(
        'uq_generation_jobs_provider_request_id',
        'generation_jobs',
        ['provider_request_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_generation_jobs_provider_request_id', table_name='generation_jobs')
    op.drop_index('ix_generation_jobs_status', table_name='generation_jobs')
    op.drop_index('ix_generation_jobs_collection_id', table_name='generation_jobs')
    op.drop_index('ix_generation_jobs_project_id', table_name='generation_jobs')
    op.drop_table('generation_jobs')

    op.drop_constraint('ck_collection_items_status', 'collection_items', type_='check')
    op.alter_column(
        'collection_items',
        'url',
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column('collection_items', 'generation_error_message')
    op.drop_column('collection_items', 'status')
