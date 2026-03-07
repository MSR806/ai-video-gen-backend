"""generation runs projection

Revision ID: 0008_generation_runs_projection
Revises: 0007_schema_driven_generation
Create Date: 2026-03-07 18:35:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0008_generation_runs_projection'
down_revision = '0007_schema_driven_generation'
branch_labels = None
depends_on = None


def _json_type(dialect_name: str) -> sa.JSON | postgresql.JSONB:
    if dialect_name == 'postgresql':
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    json_type = _json_type(dialect_name)

    op.create_table(
        'generation_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('operation_key', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('model_key', sa.String(length=128), nullable=False),
        sa.Column('endpoint_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('requested_output_count', sa.Integer(), nullable=False),
        sa.Column('inputs_json', json_type, nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('provider_request_id', sa.String(length=255), nullable=True),
        sa.Column('provider_response_json', json_type, nullable=True),
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
            (
                'status IN '
                "('QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'PARTIAL_FAILED', 'FAILED', 'CANCELLED')"
            ),
            name='ck_generation_runs_status',
        ),
        sa.CheckConstraint(
            'requested_output_count > 0',
            name='ck_generation_runs_requested_output_count_positive',
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_generation_runs_project_id',
        'generation_runs',
        ['project_id'],
        unique=False,
    )
    op.create_index('ix_generation_runs_status', 'generation_runs', ['status'], unique=False)
    op.create_index(
        'ix_generation_runs_status_updated_at',
        'generation_runs',
        ['status', 'updated_at'],
        unique=False,
    )
    op.create_index(
        'uq_generation_runs_provider_request_id',
        'generation_runs',
        ['provider_request_id'],
        unique=True,
        postgresql_where=sa.text('provider_request_id IS NOT NULL'),
        sqlite_where=sa.text('provider_request_id IS NOT NULL'),
    )
    op.create_index(
        'uq_generation_runs_idempotency',
        'generation_runs',
        ['project_id', 'idempotency_key'],
        unique=True,
        postgresql_where=sa.text('idempotency_key IS NOT NULL'),
        sqlite_where=sa.text('idempotency_key IS NOT NULL'),
    )

    op.create_table(
        'generation_run_outputs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('output_index', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('provider_output_json', json_type, nullable=True),
        sa.Column('stored_output_json', json_type, nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
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
            "status IN ('QUEUED', 'READY', 'FAILED')",
            name='ck_generation_run_outputs_status',
        ),
        sa.CheckConstraint(
            'output_index >= 0',
            name='ck_generation_run_outputs_output_index_non_negative',
        ),
        sa.ForeignKeyConstraint(['run_id'], ['generation_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'run_id',
            'output_index',
            name='uq_generation_run_outputs_run_id_output_index',
        ),
    )
    op.create_index(
        'ix_generation_run_outputs_run_id',
        'generation_run_outputs',
        ['run_id'],
        unique=False,
    )
    op.create_index(
        'ix_generation_run_outputs_status',
        'generation_run_outputs',
        ['status'],
        unique=False,
    )

    op.add_column('collection_items', sa.Column('run_id', sa.Uuid(), nullable=True))
    op.add_column(
        'collection_items',
        sa.Column('generation_run_output_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_collection_items_run_id',
        'collection_items',
        'generation_runs',
        ['run_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_collection_items_generation_run_output_id',
        'collection_items',
        'generation_run_outputs',
        ['generation_run_output_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_collection_items_run_id', 'collection_items', ['run_id'], unique=False)
    op.create_index(
        'ix_collection_items_generation_run_output_id',
        'collection_items',
        ['generation_run_output_id'],
        unique=False,
    )
    op.create_index(
        'uq_collection_items_generation_run_output_id',
        'collection_items',
        ['generation_run_output_id'],
        unique=True,
        postgresql_where=sa.text('generation_run_output_id IS NOT NULL'),
        sqlite_where=sa.text('generation_run_output_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_collection_items_generation_run_output_id',
        table_name='collection_items',
    )
    op.drop_index(
        'ix_collection_items_generation_run_output_id',
        table_name='collection_items',
    )
    op.drop_index('ix_collection_items_run_id', table_name='collection_items')
    op.drop_constraint(
        'fk_collection_items_generation_run_output_id',
        'collection_items',
        type_='foreignkey',
    )
    op.drop_constraint('fk_collection_items_run_id', 'collection_items', type_='foreignkey')
    op.drop_column('collection_items', 'generation_run_output_id')
    op.drop_column('collection_items', 'run_id')

    op.drop_index('ix_generation_run_outputs_status', table_name='generation_run_outputs')
    op.drop_index('ix_generation_run_outputs_run_id', table_name='generation_run_outputs')
    op.drop_table('generation_run_outputs')

    op.drop_index('uq_generation_runs_idempotency', table_name='generation_runs')
    op.drop_index('uq_generation_runs_provider_request_id', table_name='generation_runs')
    op.drop_index('ix_generation_runs_status_updated_at', table_name='generation_runs')
    op.drop_index('ix_generation_runs_status', table_name='generation_runs')
    op.drop_index('ix_generation_runs_project_id', table_name='generation_runs')
    op.drop_table('generation_runs')
