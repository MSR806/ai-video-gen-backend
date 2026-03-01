from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.collection import GetCollectionByIdUseCase
from ai_video_gen_backend.application.collection_item import (
    CreateCollectionItemUseCase,
    GenerateCollectionItemUseCase,
    GetCollectionItemsUseCase,
)
from ai_video_gen_backend.domain.collection_item import (
    CollectionItemCreationPayload,
    CollectionItemGenerationParams,
)
from ai_video_gen_backend.infrastructure.repositories import (
    CollectionItemSqlRepository,
    CollectionSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import get_db_session
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import (
    CollectionItemResponse,
    CollectionResponse,
    CreateCollectionItemRequest,
    GenerateCollectionItemRequest,
    GeneratedCollectionItemResponse,
)

router = APIRouter(tags=['collections'])


@router.get('/collections/{collection_id}', response_model=CollectionResponse)
def get_collection(
    collection_id: UUID,
    session: Session = Depends(get_db_session),
) -> CollectionResponse:
    use_case = GetCollectionByIdUseCase(CollectionSqlRepository(session))
    collection = use_case.execute(collection_id)
    if collection is None:
        raise ApiError(status_code=404, code='collection_not_found', message='Collection not found')
    return CollectionResponse.from_domain(collection)


@router.get('/collections/{collection_id}/items', response_model=list[CollectionItemResponse])
def get_collection_items(
    collection_id: UUID,
    session: Session = Depends(get_db_session),
) -> list[CollectionItemResponse]:
    collection_use_case = GetCollectionByIdUseCase(CollectionSqlRepository(session))
    if collection_use_case.execute(collection_id) is None:
        raise ApiError(status_code=404, code='collection_not_found', message='Collection not found')

    items_use_case = GetCollectionItemsUseCase(CollectionItemSqlRepository(session))
    return [
        CollectionItemResponse.from_domain(item) for item in items_use_case.execute(collection_id)
    ]


@router.post(
    '/collections/{collection_id}/items',
    response_model=CollectionItemResponse,
    status_code=201,
)
def create_collection_item(
    collection_id: UUID,
    request: CreateCollectionItemRequest,
    session: Session = Depends(get_db_session),
) -> CollectionItemResponse:
    collection_use_case = GetCollectionByIdUseCase(CollectionSqlRepository(session))
    collection = collection_use_case.execute(collection_id)
    if collection is None:
        raise ApiError(status_code=404, code='collection_not_found', message='Collection not found')

    if collection.project_id != request.project_id:
        raise ApiError(
            status_code=400,
            code='collection_project_mismatch',
            message='Collection does not belong to projectId in payload',
        )

    use_case = CreateCollectionItemUseCase(CollectionItemSqlRepository(session))
    payload = CollectionItemCreationPayload(
        project_id=request.project_id,
        collection_id=collection_id,
        media_type=request.media_type,
        name=request.name,
        description=request.description,
        url=request.url,
        metadata=request.metadata,
        generation_source=request.generation_source,
    )

    try:
        item = use_case.execute(payload)
    except IntegrityError as exc:
        raise ApiError(
            status_code=400,
            code='constraint_violation',
            message='Invalid item payload for collection/project relationship',
            details={'reason': str(exc.__class__.__name__)},
        ) from exc

    return CollectionItemResponse.from_domain(item)


@router.post(
    '/collections/{collection_id}/items/generate',
    response_model=GeneratedCollectionItemResponse,
)
def generate_collection_item(
    collection_id: UUID,
    request: GenerateCollectionItemRequest,
    session: Session = Depends(get_db_session),
) -> GeneratedCollectionItemResponse:
    collection_use_case = GetCollectionByIdUseCase(CollectionSqlRepository(session))
    collection = collection_use_case.execute(collection_id)
    if collection is None:
        raise ApiError(status_code=404, code='collection_not_found', message='Collection not found')

    if collection.project_id != request.project_id:
        raise ApiError(
            status_code=400,
            code='collection_project_mismatch',
            message='Collection does not belong to projectId in payload',
        )

    use_case = GenerateCollectionItemUseCase(CollectionItemSqlRepository(session))
    params = CollectionItemGenerationParams(
        prompt=request.prompt,
        aspect_ratio=request.aspect_ratio,
        media_type=request.media_type,
        project_id=request.project_id,
        collection_id=collection_id,
        reference_images=request.reference_images,
        camera_setup=request.camera_setup.to_domain() if request.camera_setup is not None else None,
        resolution=request.resolution,
        batch_size=request.batch_size,
    )
    generated = use_case.execute(params)
    return GeneratedCollectionItemResponse.from_domain(generated)
