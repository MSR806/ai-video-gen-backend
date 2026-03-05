"""schema driven generation

Revision ID: 0007_schema_driven_generation
Revises: 0006_collection_hierarchy
Create Date: 2026-03-04 22:10:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0007_schema_driven_generation'
down_revision = '0006_collection_hierarchy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_generation_jobs_operation', 'generation_jobs', type_='check')

    op.alter_column(
        'generation_jobs',
        'operation',
        new_column_name='operation_key',
        existing_type=sa.String(length=32),
    )
    op.alter_column(
        'generation_jobs',
        'request_payload',
        new_column_name='inputs_json',
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
    )
    op.alter_column(
        'generation_jobs',
        'provider_response',
        new_column_name='provider_response_json',
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
    )

    bind = op.get_bind()
    dialect_name = bind.dialect.name
    outputs_type: sa.JSON | postgresql.JSONB
    outputs_default: sa.TextClause
    if dialect_name == 'postgresql':
        outputs_type = postgresql.JSONB(astext_type=sa.Text())
        outputs_default = sa.text("'[]'::jsonb")
    else:
        outputs_type = sa.JSON()
        outputs_default = sa.text("'[]'")

    op.add_column('generation_jobs', sa.Column('endpoint_id', sa.String(length=255), nullable=True))
    op.add_column(
        'generation_jobs',
        sa.Column('outputs_json', outputs_type, nullable=False, server_default=outputs_default),
    )
    op.add_column(
        'generation_jobs',
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
    )

    op.create_index(
        'uq_generation_jobs_idempotency',
        'generation_jobs',
        ['project_id', 'collection_id', 'idempotency_key'],
        unique=True,
        postgresql_where=sa.text('idempotency_key IS NOT NULL'),
        sqlite_where=sa.text('idempotency_key IS NOT NULL'),
    )
    op.create_index(
        'ix_generation_jobs_status_updated_at',
        'generation_jobs',
        ['status', 'updated_at'],
        unique=False,
    )

    if dialect_name == 'postgresql':
        op.create_check_constraint(
            'ck_generation_jobs_outputs_array',
            'generation_jobs',
            "jsonb_typeof(outputs_json) = 'array'",
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'postgresql':
        op.drop_constraint('ck_generation_jobs_outputs_array', 'generation_jobs', type_='check')

    op.drop_index('ix_generation_jobs_status_updated_at', table_name='generation_jobs')
    op.drop_index('uq_generation_jobs_idempotency', table_name='generation_jobs')
    op.drop_column('generation_jobs', 'idempotency_key')
    op.drop_column('generation_jobs', 'outputs_json')
    op.drop_column('generation_jobs', 'endpoint_id')

    op.alter_column(
        'generation_jobs',
        'provider_response_json',
        new_column_name='provider_response',
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
    )
    op.alter_column(
        'generation_jobs',
        'inputs_json',
        new_column_name='request_payload',
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
    )
    op.alter_column(
        'generation_jobs',
        'operation_key',
        new_column_name='operation',
        existing_type=sa.String(length=64),
    )

    op.create_check_constraint(
        'ck_generation_jobs_operation',
        'generation_jobs',
        "operation IN ('TEXT_TO_IMAGE', 'IMAGE_TO_IMAGE')",
    )
