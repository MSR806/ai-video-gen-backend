from __future__ import annotations

from uuid import uuid4

import pytest

from ai_video_gen_backend.domain.generation import GenerationRequest
from ai_video_gen_backend.infrastructure.providers.fal.nano_banana_mapper import NanoBananaMapper


def test_nano_banana_mapper_builds_text_to_image_arguments() -> None:
    mapper = NanoBananaMapper()
    request = GenerationRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        operation='TEXT_TO_IMAGE',
        prompt='hello world',
        source_image_urls=None,
        model_key='nano_banana_t2i_v1',
        aspect_ratio='LANDSCAPE',
        seed=42,
    )

    arguments = mapper.to_arguments(request)

    assert arguments['prompt'] == 'hello world'
    assert arguments['aspect_ratio'] == '16:9'
    assert arguments['num_images'] == 1
    assert arguments['seed'] == 42
    assert 'image_urls' not in arguments


def test_nano_banana_mapper_builds_image_to_image_arguments() -> None:
    mapper = NanoBananaMapper()
    request = GenerationRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        operation='IMAGE_TO_IMAGE',
        prompt='edit this',
        source_image_urls=['https://example.com/source.png'],
        model_key='nano_banana_i2i_v1',
        aspect_ratio='SQUARE',
    )

    arguments = mapper.to_arguments(request)

    assert arguments['aspect_ratio'] == '1:1'
    assert arguments['image_urls'] == ['https://example.com/source.png']


def test_nano_banana_mapper_requires_source_image_for_image_to_image() -> None:
    mapper = NanoBananaMapper()
    request = GenerationRequest(
        project_id=uuid4(),
        collection_id=uuid4(),
        operation='IMAGE_TO_IMAGE',
        prompt='edit this',
        source_image_urls=None,
        model_key='nano_banana_i2i_v1',
        aspect_ratio='SQUARE',
    )

    with pytest.raises(ValueError):
        mapper.to_arguments(request)
