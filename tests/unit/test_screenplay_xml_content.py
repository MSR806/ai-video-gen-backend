from __future__ import annotations

import pytest

from ai_video_gen_backend.domain.screenplay import (
    SceneXmlValidationError,
    canonicalize_scene_xml,
    legacy_blocks_to_scene_xml,
)


def test_canonicalize_scene_xml_strips_formatting_and_keeps_text() -> None:
    content = '<scene>\n  <slugline>INT. OFFICE - DAY</slugline>\n</scene>'

    canonical = canonicalize_scene_xml(content)

    assert canonical == '<scene><slugline>INT. OFFICE - DAY</slugline></scene>'


def test_canonicalize_scene_xml_rejects_nested_elements() -> None:
    with pytest.raises(SceneXmlValidationError):
        canonicalize_scene_xml('<scene><action><b>Nested</b></action></scene>')


def test_legacy_blocks_to_scene_xml_ignores_legacy_ids() -> None:
    content = legacy_blocks_to_scene_xml(
        [
            {'id': 'legacy-1', 'type': 'slugline', 'text': 'INT. HALLWAY - NIGHT'},
            {'id': 'legacy-2', 'type': 'dialogue', 'text': 'Hello there.'},
        ]
    )

    assert content == (
        '<scene><slugline>INT. HALLWAY - NIGHT</slugline><dialogue>Hello there.</dialogue></scene>'
    )
