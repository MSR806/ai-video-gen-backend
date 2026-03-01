from __future__ import annotations

from uuid import uuid4

import pytest

from ai_video_gen_backend.domain.generation import GenerationRequest
from ai_video_gen_backend.infrastructure.providers.fal.mapper_keys import (
    NANO_BANANA_IMAGE_MAPPER_KEY,
)
from ai_video_gen_backend.infrastructure.providers.fal.model_catalog import (
    get_model_profile,
    get_model_profile_by_endpoint,
    resolve_model_key,
)
from ai_video_gen_backend.infrastructure.providers.fal.model_mapper_registry import (
    get_model_mapper,
)


def test_catalog_resolves_model_with_mapper_key() -> None:
    resolved = resolve_model_key(operation='TEXT_TO_IMAGE', model_key=None)
    profile = get_model_profile(resolved)

    assert profile.key == 'nano_banana_t2i_v1'
    assert profile.mapper_key == NANO_BANANA_IMAGE_MAPPER_KEY


def test_catalog_resolves_by_endpoint_for_provider_fallback() -> None:
    profile = get_model_profile_by_endpoint('fal-ai/nano-banana')

    assert profile.key == 'nano_banana_t2i_v1'
    assert profile.mapper_key == NANO_BANANA_IMAGE_MAPPER_KEY


def test_mapper_registry_returns_mapper_for_nano_banana() -> None:
    mapper = get_model_mapper(NANO_BANANA_IMAGE_MAPPER_KEY)
    request = GenerationRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        operation='TEXT_TO_IMAGE',
        prompt='a scenic landscape',
        aspect_ratio='LANDSCAPE',
        model_key='nano_banana_t2i_v1',
    )

    arguments = mapper.to_arguments(request)
    assert arguments['aspect_ratio'] == '16:9'
    assert arguments['num_images'] == 1


def test_mapper_registry_rejects_unknown_mapper_key() -> None:
    with pytest.raises(ValueError):
        get_model_mapper('UNKNOWN_MAPPER')
