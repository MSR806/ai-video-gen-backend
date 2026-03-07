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

    assert len(capabilities.image) == 1
    assert len(capabilities.video) == 1
    assert capabilities.image[0].model_key == 'nano_banana'
    assert capabilities.video[0].model_key == 'veo_3_1'
    assert capabilities.image[0].operations[0].fields[0].key == 'prompt'


def test_registry_resolves_model_operation_pair() -> None:
    loader = ModelRegistryLoader(ttl_seconds=300)
    registry = FalGenerationModelRegistry(loader)

    resolved = registry.resolve_operation(model_key='nano_banana', operation_key='image_to_image')

    assert resolved is not None
    assert resolved.endpoint_id == 'fal-ai/nano-banana/edit'
    assert resolved.media_type == 'image'
    assert registry.has_model(model_key='nano_banana') is True


def test_registry_ignores_disabled_models(tmp_path: Path) -> None:
    registry_path = tmp_path / 'registry.json'
    schema_path = (
        Path(__file__).resolve().parents[2]
        / 'src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json'
    )

    payload = {
        'models': [
            {
                'model_key': 'disabled_model',
                'display_name': 'Disabled Model',
                'provider': 'fal',
                'media_type': 'image',
                'enabled': False,
                'operations': [
                    {
                        'operation_key': 'text_to_image',
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
        ]
    }
    registry_path.write_text(json.dumps(payload), encoding='utf-8')

    loader = ModelRegistryLoader(
        ttl_seconds=300, registry_path=registry_path, schema_path=schema_path
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
    registry_path = tmp_path / 'registry.json'
    registry_path.write_text('{"models":[{"model_key":""}]}', encoding='utf-8')

    loader = ModelRegistryLoader(
        ttl_seconds=300, registry_path=registry_path, schema_path=schema_path
    )

    with pytest.raises(CapabilityRegistryError):
        loader.load()
