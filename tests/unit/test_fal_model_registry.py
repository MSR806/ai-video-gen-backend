from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_video_gen_backend.domain.generation import CapabilityRegistryError
from ai_video_gen_backend.infrastructure.providers.fal.model_registry_loader import (
    FalGenerationModelRegistry,
    ModelRegistryLoader,
)


def test_registry_lists_grouped_capabilities() -> None:
    loader = ModelRegistryLoader(ttl_seconds=300)
    registry = FalGenerationModelRegistry(loader)

    capabilities = registry.list_capabilities()

    assert len(capabilities.image) == 3
    assert len(capabilities.video) == 2
    assert [model.model_key for model in capabilities.image] == [
        'nano_banana',
        'nano_banana_pro',
        'nano_banana_2',
    ]
    assert capabilities.video[0].model_key == 'veo_3_1'
    assert capabilities.video[1].model_key == 'kling_video_2_6_pro'
    assert capabilities.image[0].operations[0].operation_type == 'text_to_image'
    assert capabilities.image[1].operations[0].endpoint_id == 'fal-ai/nano-banana-pro'
    assert capabilities.image[1].operations[1].endpoint_id == 'fal-ai/nano-banana-pro/edit'
    assert capabilities.image[2].operations[0].endpoint_id == 'fal-ai/nano-banana-2'
    assert capabilities.image[2].operations[1].endpoint_id == 'fal-ai/nano-banana-2/edit'
    pro_text_to_image = capabilities.image[1].operations[0]
    pro_aspect_ratio = next(
        field for field in pro_text_to_image.fields if field.key == 'aspect_ratio'
    )
    assert pro_aspect_ratio.enum is not None
    assert 'auto' in pro_aspect_ratio.enum
    pro_resolution = next(field for field in pro_text_to_image.fields if field.key == 'resolution')
    assert pro_resolution.enum == ['1K', '2K', '4K']
    assert pro_resolution.default == '1K'
    banana_2_text_to_image = capabilities.image[2].operations[0]
    banana_2_aspect_ratio = next(
        field for field in banana_2_text_to_image.fields if field.key == 'aspect_ratio'
    )
    assert banana_2_aspect_ratio.default == 'auto'
    banana_2_resolution = next(
        field for field in banana_2_text_to_image.fields if field.key == 'resolution'
    )
    assert banana_2_resolution.enum == ['0.5K', '1K', '2K', '4K']
    banana_2_limit_generations = next(
        field for field in banana_2_text_to_image.fields if field.key == 'limit_generations'
    )
    assert banana_2_limit_generations.default is True
    assert capabilities.video[0].operations[0].operation_name == 'Text to Video'
    assert capabilities.image[0].operations[0].fields[1].title == 'Number of Images'
    assert capabilities.image[0].operations[0].fields[1].minimum == 1
    assert capabilities.image[0].operations[0].fields[1].maximum == 4
    assert capabilities.image[0].operations[0].fields[-1].ui_group == 'advanced'
    image_to_image = capabilities.image[0].operations[1]
    assert image_to_image.media_groups[0].group_key == 'references'
    assert image_to_image.media_groups[0].layout == 'gallery'
    assert image_to_image.fields[2].media_group == 'references'
    first_last = next(
        operation
        for operation in capabilities.video[0].operations
        if operation.operation_key == 'first_last_frame_to_video'
    )
    assert first_last.media_groups[0].group_key == 'frames'
    assert first_last.fields[-2].media_name == 'Start'
    assert first_last.fields[-2].media_order == 1
    assert first_last.fields[-1].media_name == 'End'
    assert first_last.fields[-1].media_order == 2


def test_registry_resolves_model_operation_pair() -> None:
    loader = ModelRegistryLoader(ttl_seconds=300)
    registry = FalGenerationModelRegistry(loader)

    resolved = registry.resolve_operation(model_key='veo_3_1', operation_key='text_to_video_fast')

    assert resolved is not None
    assert resolved.endpoint_id == 'fal-ai/veo3.1/fast'
    assert resolved.media_type == 'video'
    assert resolved.operation_type == 'text_to_video'
    assert resolved.operation_name == 'Text to Video (Fast)'
    assert registry.has_model(model_key='veo_3_1') is True


def test_registry_ignores_disabled_models(tmp_path: Path) -> None:
    registry_dir = tmp_path / 'registry'
    schema_path = (
        Path(__file__).resolve().parents[2]
        / 'src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json'
    )
    registry_dir.mkdir()

    payload = {
        'sort_order': 99,
        'model_key': 'disabled_model',
        'display_name': 'Disabled Model',
        'provider': 'fal',
        'media_type': 'image',
        'enabled': False,
        'operations': [
            {
                'operation_key': 'text_to_image',
                'operation_type': 'text_to_image',
                'operation_name': 'Text to Image',
                'endpoint_id': 'fal-ai/disabled',
                'input_schema': {
                    'type': 'object',
                    'properties': {'prompt': {'type': 'string'}},
                    'required': ['prompt'],
                    'additionalProperties': False,
                },
            }
        ],
    }
    (registry_dir / 'disabled_model.json').write_text(json.dumps(payload), encoding='utf-8')

    loader = ModelRegistryLoader(
        ttl_seconds=300, registry_dir=registry_dir, schema_path=schema_path
    )
    registry = FalGenerationModelRegistry(loader)

    capabilities = registry.list_capabilities()

    assert capabilities.image == []
    assert capabilities.video == []
    assert registry.has_model(model_key='disabled_model') is False


def test_registry_loader_raises_for_invalid_payload(tmp_path: Path) -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / 'src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json'
    )
    registry_dir = tmp_path / 'registry'
    registry_dir.mkdir()
    (registry_dir / 'invalid.json').write_text('{"model_key":""}', encoding='utf-8')

    loader = ModelRegistryLoader(
        ttl_seconds=300, registry_dir=registry_dir, schema_path=schema_path
    )

    with pytest.raises(CapabilityRegistryError):
        loader.load()


def test_registry_loader_raises_for_duplicate_operation_keys(tmp_path: Path) -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / 'src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json'
    )
    registry_dir = tmp_path / 'registry'
    registry_dir.mkdir()

    payload = {
        'sort_order': 10,
        'model_key': 'duplicate_model',
        'display_name': 'Duplicate Model',
        'provider': 'fal',
        'media_type': 'video',
        'enabled': True,
        'operations': [
            {
                'operation_key': 'text_to_video',
                'operation_type': 'text_to_video',
                'operation_name': 'Text to Video',
                'endpoint_id': 'fal-ai/example/one',
                'input_schema': {
                    'type': 'object',
                    'properties': {'prompt': {'type': 'string'}},
                    'required': ['prompt'],
                    'additionalProperties': False,
                },
            },
            {
                'operation_key': 'text_to_video',
                'operation_type': 'text_to_video',
                'operation_name': 'Text to Video (Fast)',
                'endpoint_id': 'fal-ai/example/two',
                'input_schema': {
                    'type': 'object',
                    'properties': {'prompt': {'type': 'string'}},
                    'required': ['prompt'],
                    'additionalProperties': False,
                },
            },
        ],
    }
    (registry_dir / 'duplicate_model.json').write_text(json.dumps(payload), encoding='utf-8')

    loader = ModelRegistryLoader(
        ttl_seconds=300, registry_dir=registry_dir, schema_path=schema_path
    )

    with pytest.raises(CapabilityRegistryError, match='Duplicate operation_key'):
        loader.load()


def test_registry_loader_raises_for_unknown_media_group(tmp_path: Path) -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / 'src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json'
    )
    registry_dir = tmp_path / 'registry'
    registry_dir.mkdir()

    payload = {
        'sort_order': 10,
        'model_key': 'invalid_media_group',
        'display_name': 'Invalid Media Group',
        'provider': 'fal',
        'media_type': 'video',
        'enabled': True,
        'operations': [
            {
                'operation_key': 'image_to_video',
                'operation_type': 'image_to_video',
                'operation_name': 'Image to Video',
                'endpoint_id': 'fal-ai/example/image-to-video',
                'input_schema': {
                    'type': 'object',
                    'x_ui_media_groups': [
                        {'group_key': 'frames', 'layout': 'sequence', 'placement': 'top'}
                    ],
                    'properties': {
                        'image_url': {
                            'type': 'string',
                            'format': 'uri',
                            'x_ui_media_group': 'missing_group',
                        }
                    },
                    'required': ['image_url'],
                    'additionalProperties': False,
                },
            }
        ],
    }
    (registry_dir / 'invalid_media_group.json').write_text(json.dumps(payload), encoding='utf-8')

    loader = ModelRegistryLoader(
        ttl_seconds=300, registry_dir=registry_dir, schema_path=schema_path
    )

    with pytest.raises(CapabilityRegistryError, match='unknown x_ui_media_group'):
        loader.load()


def test_registry_loader_raises_for_duplicate_sequence_order(tmp_path: Path) -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / 'src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json'
    )
    registry_dir = tmp_path / 'registry'
    registry_dir.mkdir()

    payload = {
        'sort_order': 10,
        'model_key': 'duplicate_sequence_order',
        'display_name': 'Duplicate Sequence Order',
        'provider': 'fal',
        'media_type': 'video',
        'enabled': True,
        'operations': [
            {
                'operation_key': 'sequence_video',
                'operation_type': 'image_to_video',
                'operation_name': 'Sequence Video',
                'endpoint_id': 'fal-ai/example/sequence',
                'input_schema': {
                    'type': 'object',
                    'x_ui_media_groups': [
                        {'group_key': 'frames', 'layout': 'sequence', 'placement': 'top'}
                    ],
                    'properties': {
                        'start_image_url': {
                            'type': 'string',
                            'format': 'uri',
                            'x_ui_media_group': 'frames',
                            'x_ui_media_order': 1,
                        },
                        'end_image_url': {
                            'type': 'string',
                            'format': 'uri',
                            'x_ui_media_group': 'frames',
                            'x_ui_media_order': 1,
                        },
                    },
                    'required': ['start_image_url'],
                    'additionalProperties': False,
                },
            }
        ],
    }
    (registry_dir / 'duplicate_sequence_order.json').write_text(
        json.dumps(payload), encoding='utf-8'
    )

    loader = ModelRegistryLoader(
        ttl_seconds=300, registry_dir=registry_dir, schema_path=schema_path
    )

    with pytest.raises(CapabilityRegistryError, match='Duplicate x_ui_media_order'):
        loader.load()


def test_registry_loader_raises_for_invalid_gallery_field_type(tmp_path: Path) -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / 'src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json'
    )
    registry_dir = tmp_path / 'registry'
    registry_dir.mkdir()

    payload = {
        'sort_order': 10,
        'model_key': 'invalid_gallery_layout',
        'display_name': 'Invalid Gallery Layout',
        'provider': 'fal',
        'media_type': 'image',
        'enabled': True,
        'operations': [
            {
                'operation_key': 'text_to_image',
                'operation_type': 'text_to_image',
                'operation_name': 'Text to Image',
                'endpoint_id': 'fal-ai/example/text',
                'input_schema': {
                    'type': 'object',
                    'x_ui_media_groups': [
                        {'group_key': 'references', 'layout': 'gallery', 'placement': 'top'}
                    ],
                    'properties': {
                        'image_url': {
                            'type': 'string',
                            'format': 'uri',
                            'x_ui_media_group': 'references',
                        }
                    },
                    'additionalProperties': False,
                },
            }
        ],
    }
    (registry_dir / 'invalid_gallery_layout.json').write_text(json.dumps(payload), encoding='utf-8')

    loader = ModelRegistryLoader(
        ttl_seconds=300, registry_dir=registry_dir, schema_path=schema_path
    )

    with pytest.raises(CapabilityRegistryError, match='layout "gallery"'):
        loader.load()
