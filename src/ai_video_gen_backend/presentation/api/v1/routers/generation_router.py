from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.generation import (
    GenerationFinalizer,
    GetGenerationRunUseCase,
    ReconcileGenerationRunUseCase,
)
from ai_video_gen_backend.config.settings import Settings
from ai_video_gen_backend.domain.collection_item import (
    ObjectStoragePort,
    VideoThumbnailGeneratorPort,
)
from ai_video_gen_backend.domain.generation import GenerationProviderPort, MediaDownloaderPort
from ai_video_gen_backend.infrastructure.repositories import (
    CollectionItemSqlRepository,
    GenerationRunSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import (
    get_app_settings,
    get_db_session,
    get_generation_provider,
    get_media_downloader,
    get_object_storage,
    get_video_thumbnail_generator,
)
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import GenerationRunResponse

router = APIRouter(tags=['generation'])


@router.get('/generation-runs/{run_id}', response_model=GenerationRunResponse)
def get_generation_run(
    run_id: UUID,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    generation_provider: GenerationProviderPort = Depends(get_generation_provider),
    object_storage: ObjectStoragePort = Depends(get_object_storage),
    media_downloader: MediaDownloaderPort = Depends(get_media_downloader),
    video_thumbnail_generator: VideoThumbnailGeneratorPort = Depends(get_video_thumbnail_generator),
) -> GenerationRunResponse:
    collection_item_repository = CollectionItemSqlRepository(session)
    generation_run_repository = GenerationRunSqlRepository(session)
    generation_finalizer = GenerationFinalizer(
        collection_item_repository=collection_item_repository,
        generation_run_repository=generation_run_repository,
        object_storage=object_storage,
        media_downloader=media_downloader,
        video_thumbnail_generator=video_thumbnail_generator,
        max_download_bytes=settings.generation_result_max_download_mb * 1024 * 1024,
    )
    reconcile_use_case = ReconcileGenerationRunUseCase(
        generation_run_repository=generation_run_repository,
        generation_provider=generation_provider,
        generation_finalizer=generation_finalizer,
    )
    use_case = GetGenerationRunUseCase(
        generation_run_repository,
        reconcile_use_case,
        reconcile_after_seconds=settings.generation_status_reconcile_after_seconds,
    )

    run = use_case.execute(run_id)
    if run is None:
        raise ApiError(
            status_code=404,
            code='generation_run_not_found',
            message='Generation run not found',
        )

    run_outputs = generation_run_repository.list_outputs_by_run_id(run.id)
    collection_items = collection_item_repository.get_items_by_run_id(run.id)
    return GenerationRunResponse.from_domain(run, run_outputs, collection_items)
