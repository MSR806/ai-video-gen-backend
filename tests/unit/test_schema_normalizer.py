from __future__ import annotations

from typing import cast

import pytest

from ai_video_gen_backend.domain.generation import CapabilityRegistryError
from ai_video_gen_backend.domain.types import JsonObject
from ai_video_gen_backend.infrastructure.providers.fal.schema_normalizer import (
    normalize_operation_schema,
)


def test_rejects_field_media_group_without_top_level_groups() -> None:
    schema = {
        'type': 'object',
        'properties': {
            'image_url': {
                'type': 'string',
                'format': 'uri',
                'x_ui_media_group': 'inputs',
            }
        },
    }

    with pytest.raises(CapabilityRegistryError, match='without x_ui_media_groups'):
        normalize_operation_schema(cast(JsonObject, schema))


def test_rejects_sequence_media_group_with_duplicate_order() -> None:
    schema = {
        'type': 'object',
        'x_ui_media_groups': [{'group_key': 'inputs', 'layout': 'sequence', 'placement': 'top'}],
        'properties': {
            'image_url': {
                'type': 'string',
                'format': 'uri',
                'x_ui_media_group': 'inputs',
                'x_ui_media_order': 1,
            },
            'second_image_url': {
                'type': 'string',
                'format': 'uri',
                'x_ui_media_group': 'inputs',
                'x_ui_media_order': 1,
            },
        },
    }

    with pytest.raises(CapabilityRegistryError, match='Duplicate x_ui_media_order 1'):
        normalize_operation_schema(cast(JsonObject, schema))


def test_rejects_gallery_media_group_with_non_uri_items() -> None:
    schema = {
        'type': 'object',
        'x_ui_media_groups': [{'group_key': 'gallery', 'layout': 'gallery', 'placement': 'top'}],
        'properties': {
            'images': {
                'type': 'array',
                'items': {'type': 'string'},
                'x_ui_media_group': 'gallery',
            }
        },
    }

    with pytest.raises(CapabilityRegistryError, match='layout "gallery"'):
        normalize_operation_schema(cast(JsonObject, schema))


def test_rejects_non_list_media_groups() -> None:
    schema = {
        'type': 'object',
        'x_ui_media_groups': {'group_key': 'inputs', 'layout': 'single', 'placement': 'top'},
    }

    with pytest.raises(CapabilityRegistryError, match='x_ui_media_groups must be a list'):
        normalize_operation_schema(cast(JsonObject, schema))


def test_rejects_media_group_with_invalid_placement() -> None:
    schema = {
        'type': 'object',
        'x_ui_media_groups': [{'group_key': 'inputs', 'layout': 'single', 'placement': 'left'}],
        'properties': {
            'image_url': {
                'type': 'string',
                'format': 'uri',
                'x_ui_media_group': 'inputs',
            }
        },
    }

    with pytest.raises(CapabilityRegistryError, match='placement must be one of'):
        normalize_operation_schema(cast(JsonObject, schema))


def test_rejects_media_name_without_media_group() -> None:
    schema = {
        'type': 'object',
        'properties': {
            'image_url': {
                'type': 'string',
                'format': 'uri',
                'x_ui_media_name': 'Cover image',
            }
        },
    }

    with pytest.raises(CapabilityRegistryError, match='x_ui_media_name without x_ui_media_group'):
        normalize_operation_schema(cast(JsonObject, schema))


def test_accepts_valid_gallery_media_group() -> None:
    schema = {
        'type': 'object',
        'x_ui_media_groups': [{'group_key': 'gallery', 'layout': 'gallery', 'placement': 'top'}],
        'properties': {
            'images': {
                'type': 'array',
                'items': {'type': 'string', 'format': 'uri'},
                'x_ui_media_group': 'gallery',
                'x_ui_media_name': 'Reference images',
            }
        },
    }

    required, fields, groups = normalize_operation_schema(cast(JsonObject, schema))

    assert required == []
    assert len(fields) == 1
    assert fields[0].media_group == 'gallery'
    assert groups[0].group_key == 'gallery'
