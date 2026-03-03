from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.generation import (
    GenerationFinalizationError,
    GenerationFinalizer,
    HandleFalWebhookUseCase,
)
from ai_video_gen_backend.config.settings import Settings
from ai_video_gen_backend.domain.collection_item import ObjectStoragePort
from ai_video_gen_backend.domain.generation import GenerationProviderPort, MediaDownloaderPort
from ai_video_gen_backend.infrastructure.repositories import (
    CollectionItemSqlRepository,
    GenerationJobSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import (
    get_app_settings,
    get_db_session,
    get_generation_provider,
    get_media_downloader,
    get_object_storage,
)
from ai_video_gen_backend.presentation.api.errors import ApiError

router = APIRouter(tags=['provider-webhooks'])


@router.post('/provider-webhooks/fal')
async def handle_fal_webhook(
    request: Request,
    token: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    generation_provider: GenerationProviderPort = Depends(get_generation_provider),
    object_storage: ObjectStoragePort = Depends(get_object_storage),
    media_downloader: MediaDownloaderPort = Depends(get_media_downloader),
) -> dict[str, bool]:
    if token != settings.generation_webhook_token:
        raise ApiError(status_code=401, code='unauthorized_webhook', message='Unauthorized webhook')

    payload_raw = await request.json()
    if not isinstance(payload_raw, dict):
        raise ApiError(
            status_code=400,
            code='invalid_webhook_payload',
            message='Invalid webhook payload',
        )

    payload = {str(k): v for k, v in payload_raw.items()}

    generation_job_repository = GenerationJobSqlRepository(session)
    generation_finalizer = GenerationFinalizer(
        collection_item_repository=CollectionItemSqlRepository(session),
        generation_job_repository=generation_job_repository,
        object_storage=object_storage,
        media_downloader=media_downloader,
        max_download_bytes=settings.generation_result_max_download_mb * 1024 * 1024,
    )
    use_case = HandleFalWebhookUseCase(
        generation_job_repository=generation_job_repository,
        generation_provider=generation_provider,
        generation_finalizer=generation_finalizer,
    )

    try:
        handled = use_case.execute(payload)
    except GenerationFinalizationError as exc:
        raise ApiError(
            status_code=500,
            code='generation_finalize_failed',
            message=str(exc),
        ) from exc

    return {'handled': handled}
