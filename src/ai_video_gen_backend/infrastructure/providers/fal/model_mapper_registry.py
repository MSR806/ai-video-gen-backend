from __future__ import annotations

from typing import Protocol

from ai_video_gen_backend.domain.generation import GenerationRequest
from ai_video_gen_backend.infrastructure.providers.fal.mapper_keys import (
    NANO_BANANA_IMAGE_MAPPER_KEY,
)
from ai_video_gen_backend.infrastructure.providers.fal.nano_banana_mapper import NanoBananaMapper


class FalModelMapper(Protocol):
    def to_arguments(self, request: GenerationRequest) -> dict[str, object]: ...

    def extract_output_url(self, payload: dict[str, object]) -> str | None: ...


MAPPER_REGISTRY: dict[str, FalModelMapper] = {
    NANO_BANANA_IMAGE_MAPPER_KEY: NanoBananaMapper(),
}


def get_model_mapper(mapper_key: str) -> FalModelMapper:
    mapper = MAPPER_REGISTRY.get(mapper_key)
    if mapper is None:
        msg = f'Unsupported mapper key: {mapper_key}'
        raise ValueError(msg)
    return mapper
