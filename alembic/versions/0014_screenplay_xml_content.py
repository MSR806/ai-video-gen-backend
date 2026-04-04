"""migrate screenplay scene content from json to xml

Revision ID: 0014_screenplay_xml_content
Revises: 0013_drop_legacy_scenes
Create Date: 2026-04-04 00:00:02
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from xml.etree import ElementTree as ET

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0014_screenplay_xml_content'
down_revision = '0013_drop_legacy_scenes'
branch_labels = None
depends_on = None

_allowed_scene_block_tags: tuple[str, ...] = (
    'slugline',
    'action',
    'character',
    'parenthetical',
    'dialogue',
    'transition',
)


def upgrade() -> None:
    op.add_column('screenplay_scenes', sa.Column('content_xml', sa.Text(), nullable=True))

    connection = op.get_bind()
    scenes_table = sa.table(
        'screenplay_scenes',
        sa.column('id', sa.Uuid()),
        sa.column('content_json', sa.JSON()),
        sa.column('content_xml', sa.Text()),
    )
    rows = connection.execute(sa.select(scenes_table.c.id, scenes_table.c.content_json)).mappings()
    for row in rows:
        content_xml = _legacy_blocks_to_scene_xml(row['content_json'])
        connection.execute(
            sa.update(scenes_table)
            .where(scenes_table.c.id == row['id'])
            .values(content_xml=content_xml)
        )

    op.alter_column('screenplay_scenes', 'content_xml', nullable=False)
    op.drop_column('screenplay_scenes', 'content_json')


def downgrade() -> None:
    op.add_column('screenplay_scenes', sa.Column('content_json', sa.JSON(), nullable=True))

    connection = op.get_bind()
    scenes_table = sa.table(
        'screenplay_scenes',
        sa.column('id', sa.Uuid()),
        sa.column('content_json', sa.JSON()),
        sa.column('content_xml', sa.Text()),
    )
    rows = connection.execute(sa.select(scenes_table.c.id, scenes_table.c.content_xml)).mappings()
    for row in rows:
        content_json = _scene_xml_to_legacy_blocks(row['content_xml'])
        connection.execute(
            sa.update(scenes_table)
            .where(scenes_table.c.id == row['id'])
            .values(content_json=content_json)
        )

    op.alter_column('screenplay_scenes', 'content_json', nullable=False)
    op.drop_column('screenplay_scenes', 'content_xml')


def _legacy_blocks_to_scene_xml(blocks: Sequence[object]) -> str:
    root = ET.Element('scene')

    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, Mapping):
            raise ValueError(f'legacy block at index {index} must be an object')

        block_type = block.get('type')
        text = block.get('text')
        if not isinstance(block_type, str) or block_type not in _allowed_scene_block_tags:
            raise ValueError(f'legacy block at index {index} has invalid type {block_type!r}')
        if not isinstance(text, str):
            raise ValueError(f'legacy block at index {index} text must be a string')

        child = ET.SubElement(root, block_type)
        child.text = text

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)


def _scene_xml_to_legacy_blocks(content_xml: str) -> list[dict[str, str]]:
    root = ET.fromstring(content_xml)  # noqa: S314
    if root.tag != 'scene':
        raise ValueError('scene XML root must be <scene>')

    blocks: list[dict[str, str]] = []
    for index, child in enumerate(root, start=1):
        if child.tag not in _allowed_scene_block_tags:
            raise ValueError(f'invalid scene block tag <{child.tag}>')
        if len(child) != 0:
            raise ValueError(f'scene block <{child.tag}> must contain only text')

        blocks.append(
            {
                'id': f'block-{index}',
                'type': child.tag,
                'text': child.text or '',
            }
        )

    return blocks
