from __future__ import annotations

from ai_video_gen_backend.domain.generation import GenerationRequest
from ai_video_gen_backend.infrastructure.providers.fal.model_catalog import ASPECT_RATIO_MAP


class NanoBananaMapper:
    def to_arguments(self, request: GenerationRequest) -> dict[str, object]:
        arguments: dict[str, object] = {
            'prompt': request.prompt,
            'num_images': 1,
            'aspect_ratio': ASPECT_RATIO_MAP[request.aspect_ratio],
            'output_format': 'png',
        }
        if request.seed is not None:
            arguments['seed'] = request.seed

        if request.operation == 'IMAGE_TO_IMAGE':
            if request.source_image_urls is None or len(request.source_image_urls) == 0:
                msg = 'image_to_image requires source image URLs'
                raise ValueError(msg)
            arguments['image_urls'] = request.source_image_urls

        return arguments

    def extract_output_url(self, payload: dict[str, object]) -> str | None:
        candidates: list[dict[str, object]] = []
        nested_payload = payload.get('payload')
        if isinstance(nested_payload, dict):
            candidates.append(nested_payload)
        candidates.append(payload)

        for candidate in candidates:
            images = candidate.get('images')
            if isinstance(images, list) and len(images) > 0:
                first = images[0]
                if isinstance(first, dict):
                    url = first.get('url')
                    if isinstance(url, str) and len(url.strip()) > 0:
                        return url

        return None
