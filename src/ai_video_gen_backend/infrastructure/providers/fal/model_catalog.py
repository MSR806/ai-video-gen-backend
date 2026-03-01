from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_video_gen_backend.domain.generation import GenerationOperation
from ai_video_gen_backend.infrastructure.providers.fal.mapper_keys import (
    NANO_BANANA_IMAGE_MAPPER_KEY,
)


@dataclass(frozen=True, slots=True)
class FalModelProfile:
    key: str
    operation: GenerationOperation
    endpoint_id: str
    mapper_key: str
    enabled: bool


MODEL_CATALOG: dict[str, FalModelProfile] = {
    'nano_banana_t2i_v1': FalModelProfile(
        key='nano_banana_t2i_v1',
        operation='TEXT_TO_IMAGE',
        endpoint_id='fal-ai/nano-banana',
        mapper_key=NANO_BANANA_IMAGE_MAPPER_KEY,
        enabled=True,
    ),
    'nano_banana_i2i_v1': FalModelProfile(
        key='nano_banana_i2i_v1',
        operation='IMAGE_TO_IMAGE',
        endpoint_id='fal-ai/nano-banana/edit',
        mapper_key=NANO_BANANA_IMAGE_MAPPER_KEY,
        enabled=True,
    ),
}

DEFAULT_MODEL_BY_OPERATION: dict[GenerationOperation, str] = {
    'TEXT_TO_IMAGE': 'nano_banana_t2i_v1',
    'IMAGE_TO_IMAGE': 'nano_banana_i2i_v1',
}

AspectRatio = Literal['SQUARE', 'PORTRAIT', 'LANDSCAPE']


ASPECT_RATIO_MAP: dict[AspectRatio, str] = {
    'SQUARE': '1:1',
    'PORTRAIT': '9:16',
    'LANDSCAPE': '16:9',
}


def resolve_model_key(
    *,
    operation: GenerationOperation,
    model_key: str | None,
) -> str:
    key = model_key if model_key is not None else DEFAULT_MODEL_BY_OPERATION[operation]
    profile = MODEL_CATALOG.get(key)
    if profile is None or not profile.enabled or profile.operation != operation:
        msg = f'Unsupported model key: {key}'
        raise ValueError(msg)
    return key


def get_model_profile(model_key: str) -> FalModelProfile:
    profile = MODEL_CATALOG.get(model_key)
    if profile is None or not profile.enabled:
        msg = f'Unsupported model key: {model_key}'
        raise ValueError(msg)
    return profile


def get_model_profile_by_endpoint(endpoint_id: str) -> FalModelProfile:
    matches = [
        profile
        for profile in MODEL_CATALOG.values()
        if profile.enabled and profile.endpoint_id == endpoint_id
    ]
    if len(matches) != 1:
        msg = f'Unsupported or ambiguous endpoint: {endpoint_id}'
        raise ValueError(msg)
    return matches[0]
