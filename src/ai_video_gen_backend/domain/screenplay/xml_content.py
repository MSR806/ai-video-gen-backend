from __future__ import annotations

from collections.abc import Mapping, Sequence
from xml.etree import ElementTree as ET

ALLOWED_SCENE_BLOCK_TAGS: tuple[str, ...] = (
    'slugline',
    'action',
    'character',
    'parenthetical',
    'dialogue',
    'transition',
)


class SceneXmlValidationError(ValueError):
    pass


def canonicalize_scene_xml(content: str) -> str:
    root = _parse_scene_xml(content)
    canonical_root = ET.Element('scene')

    for child in root:
        _validate_scene_block(child)

        canonical_child = ET.SubElement(canonical_root, child.tag)
        canonical_child.text = child.text or ''

    return ET.tostring(canonical_root, encoding='unicode', short_empty_elements=False)


def validate_scene_xml(content: str) -> None:
    canonicalize_scene_xml(content)


def legacy_blocks_to_scene_xml(blocks: Sequence[object]) -> str:
    root = ET.Element('scene')

    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, Mapping):
            raise SceneXmlValidationError(f'legacy block at index {index} must be an object')

        block_type = block.get('type')
        text = block.get('text')
        if not isinstance(block_type, str) or block_type not in ALLOWED_SCENE_BLOCK_TAGS:
            raise SceneXmlValidationError(
                f'legacy block at index {index} has invalid type {block_type!r}'
            )
        if not isinstance(text, str):
            raise SceneXmlValidationError(f'legacy block at index {index} text must be a string')

        child = ET.SubElement(root, block_type)
        child.text = text

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)


def _parse_scene_xml(content: str) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))  # noqa: S314
    try:
        root = ET.fromstring(content, parser=parser)  # noqa: S314
    except ET.ParseError as exc:
        raise SceneXmlValidationError('scene XML is malformed') from exc

    if root.tag != 'scene':
        raise SceneXmlValidationError('scene XML root must be <scene>')

    if root.attrib:
        raise SceneXmlValidationError('<scene> must not include attributes')

    if root.text is not None and root.text.strip() != '':
        raise SceneXmlValidationError('<scene> must only contain scene block elements')

    return root


def _validate_scene_block(child: ET.Element) -> None:
    if not isinstance(child.tag, str):
        raise SceneXmlValidationError(
            'scene XML comments and processing instructions are not allowed'
        )

    if child.tag not in ALLOWED_SCENE_BLOCK_TAGS:
        raise SceneXmlValidationError(f'invalid scene block tag <{child.tag}>')

    if child.attrib:
        raise SceneXmlValidationError(f'scene block <{child.tag}> must not include attributes')

    # Blocks are text-only by contract. Nested tags are rejected to avoid mixed
    # structures that drift from the screenplay XML contract.
    if len(child) != 0:
        raise SceneXmlValidationError(f'scene block <{child.tag}> must contain only text')

    if child.tail is not None and child.tail.strip() != '':
        raise SceneXmlValidationError('scene XML must not include text outside block elements')
