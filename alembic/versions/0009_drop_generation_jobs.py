"""drop generation jobs

Revision ID: 0009_drop_generation_jobs
Revises: 0008_generation_runs_projection
Create Date: 2026-03-07 18:45:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0009_drop_generation_jobs'
down_revision = '0008_generation_runs_projection'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index('ix_collection_items_job_id', table_name='collection_items')
    op.drop_column('collection_items', 'job_id')
    op.drop_table('generation_jobs')


def downgrade() -> None:
    op.create_table(
        'generation_jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('collection_id', sa.Uuid(), nullable=False),
        sa.Column('collection_item_id', sa.Uuid(), nullable=True),
        sa.Column('operation_key', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('model_key', sa.String(length=128), nullable=False),
        sa.Column('endpoint_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('inputs_json', sa.JSON(), nullable=False),
        sa.Column('outputs_json', sa.JSON(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('provider_request_id', sa.String(length=255), nullable=True),
        sa.Column('provider_response_json', sa.JSON(), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name='ck_generation_jobs_status',
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['collection_item_id'],
            ['collection_items.id'],
            ondelete='SET NULL',
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
        'ix_generation_jobs_status_updated_at',
        'generation_jobs',
        ['status', 'updated_at'],
        unique=False,
    )
    op.create_index(
        'uq_generation_jobs_provider_request_id',
        'generation_jobs',
        ['provider_request_id'],
        unique=True,
    )
    op.create_index(
        'uq_generation_jobs_idempotency',
        'generation_jobs',
        ['project_id', 'collection_id', 'idempotency_key'],
        unique=True,
    )

    op.add_column('collection_items', sa.Column('job_id', sa.Uuid(), nullable=True))
    op.create_index('ix_collection_items_job_id', 'collection_items', ['job_id'], unique=False)
