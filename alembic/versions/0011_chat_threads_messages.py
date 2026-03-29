"""add chat threads and messages

Revision ID: 0011_chat_threads_messages
Revises: 0010_collection_item_favorite
Create Date: 2026-03-29 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0011_chat_threads_messages'
down_revision = '0010_collection_item_favorite'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chat_threads',
        sa.Column('id', sa.Uuid(), nullable=False),
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
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('thread_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('images_json', sa.JSON(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name='ck_chat_messages_role'),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_thread_id', 'chat_messages', ['thread_id'], unique=False)
    op.create_index(
        'ix_chat_messages_thread_created_at',
        'chat_messages',
        ['thread_id', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_chat_messages_thread_created_at', table_name='chat_messages')
    op.drop_index('ix_chat_messages_thread_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_table('chat_threads')
