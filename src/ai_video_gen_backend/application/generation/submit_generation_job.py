from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from ai_video_gen_backend.domain.collection_item import CollectionItemCreationPayload
from ai_video_gen_backend.domain.generation import (
    GenerationJobRepositoryPort,
    GenerationProviderPort,
    GenerationRequest,
)
from ai_video_gen_backend.infrastructure.providers.fal import resolve_model_key
from ai_video_gen_backend.infrastructure.repositories import CollectionItemSqlRepository


class UnsupportedModelError(Exception):
    """Raised when model key is not allowed."""


class InvalidGenerationRequestError(Exception):
    """Raised when generation request payload is invalid."""


class SubmitGenerationJobUseCase:
    def __init__(
        self,
        collection_item_repository: CollectionItemSqlRepository,
        generation_job_repository: GenerationJobRepositoryPort,
        generation_provider: GenerationProviderPort,
        *,
        webhook_url: str,
    ) -> None:
        self._collection_item_repository = collection_item_repository
        self._generation_job_repository = generation_job_repository
        self._generation_provider = generation_provider
        self._webhook_url = webhook_url

    def execute(self, request: GenerationRequest) -> tuple[UUID, UUID, str]:
        self._validate_request(request)

        try:
            resolved_model_key = resolve_model_key(
                operation=request.operation,
                model_key=request.model_key,
            )
        except ValueError as exc:
            raise UnsupportedModelError from exc

        request = replace(request, model_key=resolved_model_key)

        placeholder_item = self._collection_item_repository.create_item(
            CollectionItemCreationPayload(
                project_id=request.project_id,
                collection_id=request.collection_id,
                media_type='image',
                name=self._item_name(request.prompt),
                description='AI generation in progress',
                url=None,
                metadata={
                    'operation': request.operation,
                    'modelKey': resolved_model_key,
                    'thumbnailUrl': '',
                    'width': 0,
                    'height': 0,
                    'format': 'png',
                },
                generation_source='fal',
                status='GENERATING',
            )
        )

        generation_job = self._generation_job_repository.create_job(
            project_id=request.project_id,
            collection_id=request.collection_id,
            collection_item_id=placeholder_item.id,
            operation=request.operation,
            provider='fal',
            model_key=resolved_model_key,
            request_payload={
                'prompt': request.prompt,
                'operation': request.operation,
                'aspectRatio': request.aspect_ratio,
                'sourceImageUrls': request.source_image_urls,
                'seed': request.seed,
                'idempotencyKey': request.idempotency_key,
            },
        )

        try:
            submission = self._generation_provider.submit(request, webhook_url=self._webhook_url)
            submitted = self._generation_job_repository.mark_submitted(
                generation_job.id,
                provider_request_id=submission.provider_request_id,
            )
            return submitted.id, placeholder_item.id, submitted.status
        except Exception as exc:
            self._generation_job_repository.mark_failed(
                generation_job.id,
                error_code='provider_submit_failed',
                error_message=str(exc),
            )
            self._collection_item_repository.mark_generated_item_failed(
                item_id=placeholder_item.id,
                error_message='Failed to submit generation request',
            )
            raise

    def _validate_request(self, request: GenerationRequest) -> None:
        if request.operation == 'TEXT_TO_IMAGE' and request.source_image_urls not in (None, []):
            raise InvalidGenerationRequestError('text_to_image does not accept sourceImageUrls')

        if request.operation == 'IMAGE_TO_IMAGE' and (
            request.source_image_urls is None or len(request.source_image_urls) != 1
        ):
            raise InvalidGenerationRequestError(
                'image_to_image requires exactly one source image URL'
            )

    def _item_name(self, prompt: str) -> str:
        trimmed = prompt.strip()
        if len(trimmed) == 0:
            return 'Generated Image'
        return trimmed[:80]
