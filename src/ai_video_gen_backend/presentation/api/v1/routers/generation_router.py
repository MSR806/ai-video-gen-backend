from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.generation import (
    GenerationFinalizer,
    GetGenerationJobUseCase,
    ListGenerationJobsUseCase,
    ReconcileGenerationJobUseCase,
)
from ai_video_gen_backend.config.settings import Settings
from ai_video_gen_backend.domain.collection_item import ObjectStoragePort
from ai_video_gen_backend.domain.generation import GenerationProviderPort
from ai_video_gen_backend.infrastructure.repositories import (
    CollectionItemSqlRepository,
    GenerationJobSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import (
    get_app_settings,
    get_db_session,
    get_generation_provider,
    get_object_storage,
)
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import GenerationJobResponse

router = APIRouter(tags=['generation'])

GenerationJobStatusQuery = Literal['QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED']


@router.get('/generation-jobs', response_model=list[GenerationJobResponse])
def list_generation_jobs(
    collection_id: UUID | None = Query(default=None, alias='collectionId'),
    project_id: UUID | None = Query(default=None, alias='projectId'),
    status: list[GenerationJobStatusQuery] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    generation_provider: GenerationProviderPort = Depends(get_generation_provider),
    object_storage: ObjectStoragePort = Depends(get_object_storage),
) -> list[GenerationJobResponse]:
    if collection_id is None and project_id is None:
        raise ApiError(
            status_code=400,
            code='validation_error',
            message='collectionId or projectId is required',
        )

    generation_job_repository = GenerationJobSqlRepository(session)
    generation_finalizer = GenerationFinalizer(
        collection_item_repository=CollectionItemSqlRepository(session),
        generation_job_repository=generation_job_repository,
        object_storage=object_storage,
        max_download_bytes=settings.generation_result_max_download_mb * 1024 * 1024,
    )
    reconcile_use_case = ReconcileGenerationJobUseCase(
        generation_job_repository=generation_job_repository,
        generation_provider=generation_provider,
        generation_finalizer=generation_finalizer,
    )
    use_case = ListGenerationJobsUseCase(
        generation_job_repository,
        reconcile_use_case,
        reconcile_after_seconds=settings.generation_status_reconcile_after_seconds,
    )

    jobs = use_case.execute(
        collection_id=collection_id,
        project_id=project_id,
        statuses=status,
        limit=limit,
    )
    return [GenerationJobResponse.from_domain(job) for job in jobs]


@router.get('/generation-jobs/{job_id}', response_model=GenerationJobResponse)
def get_generation_job(
    job_id: UUID,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    generation_provider: GenerationProviderPort = Depends(get_generation_provider),
    object_storage: ObjectStoragePort = Depends(get_object_storage),
) -> GenerationJobResponse:
    generation_job_repository = GenerationJobSqlRepository(session)
    generation_finalizer = GenerationFinalizer(
        collection_item_repository=CollectionItemSqlRepository(session),
        generation_job_repository=generation_job_repository,
        object_storage=object_storage,
        max_download_bytes=settings.generation_result_max_download_mb * 1024 * 1024,
    )
    reconcile_use_case = ReconcileGenerationJobUseCase(
        generation_job_repository=generation_job_repository,
        generation_provider=generation_provider,
        generation_finalizer=generation_finalizer,
    )
    use_case = GetGenerationJobUseCase(
        generation_job_repository,
        reconcile_use_case,
        reconcile_after_seconds=settings.generation_status_reconcile_after_seconds,
    )

    job = use_case.execute(job_id)
    if job is None:
        raise ApiError(
            status_code=404,
            code='generation_job_not_found',
            message='Generation job not found',
        )

    return GenerationJobResponse.from_domain(job)
