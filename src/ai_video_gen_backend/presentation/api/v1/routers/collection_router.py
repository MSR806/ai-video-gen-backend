from __future__ import annotations

import json
import os
from contextlib import suppress
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.collection import (
    GetChildCollectionsUseCase,
    GetCollectionByIdUseCase,
)
from ai_video_gen_backend.application.collection_item import (
    CreateCollectionItemUseCase,
    DeleteCollectionItemUseCase,
    GetCollectionItemByIdUseCase,
    GetCollectionItemsUseCase,
    SetCollectionItemFavoriteUseCase,
    UploadCollectionItemUseCase,
)
from ai_video_gen_backend.application.generation import (
    GenerationInputValidator,
    SubmitGenerationRunUseCase,
)
from ai_video_gen_backend.config.settings import Settings
from ai_video_gen_backend.domain.collection_item import (
    CollectionItemCreationPayload,
    JsonObject,
    ObjectStoragePort,
    VideoThumbnailGeneratorPort,
)
from ai_video_gen_backend.domain.generation import (
    GenerationCapabilityRegistryPort,
    GenerationProviderPort,
    GenerationRunRequest,
)
from ai_video_gen_backend.infrastructure.repositories import (
    CollectionItemSqlRepository,
    CollectionSqlRepository,
    GenerationRunSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import (
    get_app_settings,
    get_db_session,
    get_generation_capability_registry,
    get_generation_input_validator,
    get_generation_provider,
    get_object_storage,
    get_video_thumbnail_generator,
)
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import (
    CollectionContentsResponse,
    CollectionItemReadResponse,
    CollectionItemResponse,
    CollectionResponse,
    CreateCollectionItemRequest,
    GenerationRunSubmitRequest,
    GenerationRunSubmitResponse,
    SetCollectionItemFavoriteRequest,
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


@router.get('/collections/{collection_id}/items', response_model=CollectionContentsResponse)
def get_collection_items(
    collection_id: UUID,
    session: Session = Depends(get_db_session),
) -> CollectionContentsResponse:
    collection_use_case = GetCollectionByIdUseCase(CollectionSqlRepository(session))
    if collection_use_case.execute(collection_id) is None:
        raise ApiError(status_code=404, code='collection_not_found', message='Collection not found')

    items_use_case = GetCollectionItemsUseCase(CollectionItemSqlRepository(session))
    child_collections_use_case = GetChildCollectionsUseCase(CollectionSqlRepository(session))
    return CollectionContentsResponse(
        items=[
            CollectionItemReadResponse.from_domain(item)
            for item in items_use_case.execute(collection_id)
        ],
        child_collections=[
            CollectionResponse.from_domain(collection)
            for collection in child_collections_use_case.execute(collection_id)
        ],
    )


@router.get('/collection-items/{item_id}', response_model=CollectionItemReadResponse)
def get_collection_item_by_id(
    item_id: UUID,
    session: Session = Depends(get_db_session),
) -> CollectionItemReadResponse:
    use_case = GetCollectionItemByIdUseCase(CollectionItemSqlRepository(session))
    item = use_case.execute(item_id)
    if item is None:
        raise ApiError(
            status_code=404,
            code='collection_item_not_found',
            message='Collection item not found',
        )

    return CollectionItemReadResponse.from_domain(item)


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
    item = use_case.execute(payload)

    return CollectionItemResponse.from_domain(item)


@router.post(
    '/collections/{collection_id}/items/upload',
    response_model=CollectionItemResponse,
    status_code=201,
)
def upload_collection_item(
    collection_id: UUID,
    project_id_raw: str = Form(..., alias='projectId'),
    name: str | None = Form(default=None),
    description: str | None = Form(default=''),
    metadata_raw: str | None = Form(default=None, alias='metadata'),
    file: UploadFile | None = File(default=None),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    object_storage: ObjectStoragePort = Depends(get_object_storage),
    video_thumbnail_generator: VideoThumbnailGeneratorPort = Depends(get_video_thumbnail_generator),
) -> CollectionItemResponse:
    if file is None:
        raise ApiError(
            status_code=400,
            code='validation_error',
            message='Request validation failed',
            details={'errors': [{'loc': ['body', 'file'], 'msg': 'Field required'}]},
        )

    try:
        project_id = UUID(project_id_raw)
    except ValueError as exc:
        raise ApiError(
            status_code=400,
            code='validation_error',
            message='Request validation failed',
            details={
                'errors': [{'loc': ['body', 'projectId'], 'msg': 'Invalid UUID format'}],
            },
        ) from exc

    collection_use_case = GetCollectionByIdUseCase(CollectionSqlRepository(session))
    collection = collection_use_case.execute(collection_id)
    if collection is None:
        raise ApiError(status_code=404, code='collection_not_found', message='Collection not found')

    if collection.project_id != project_id:
        raise ApiError(
            status_code=400,
            code='collection_project_mismatch',
            message='Collection does not belong to projectId in payload',
        )

    parsed_metadata = _parse_upload_metadata(metadata_raw)
    content_type = file.content_type or ''
    file_size = _file_size(file)

    upload_use_case = UploadCollectionItemUseCase(
        CollectionItemSqlRepository(session),
        object_storage,
        video_thumbnail_generator,
        max_upload_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        allowed_mime_prefixes=settings.allowed_upload_mime_prefixes,
    )

    try:
        item = upload_use_case.execute(
            project_id=project_id,
            collection_id=collection_id,
            filename=file.filename or 'upload.bin',
            content_type=content_type,
            file_stream=file.file,
            size_bytes=file_size,
            name=name,
            description=description,
            metadata=parsed_metadata,
        )
    finally:
        with suppress(Exception):
            file.file.close()

    return CollectionItemResponse.from_domain(item)


@router.delete('/collections/{collection_id}/items/{item_id}', status_code=204)
def delete_collection_item(
    collection_id: UUID,
    item_id: UUID,
    session: Session = Depends(get_db_session),
    object_storage: ObjectStoragePort = Depends(get_object_storage),
) -> None:
    collection_use_case = GetCollectionByIdUseCase(CollectionSqlRepository(session))
    if collection_use_case.execute(collection_id) is None:
        raise ApiError(status_code=404, code='collection_not_found', message='Collection not found')

    use_case = DeleteCollectionItemUseCase(CollectionItemSqlRepository(session), object_storage)
    deleted = use_case.execute(collection_id=collection_id, item_id=item_id)

    if not deleted:
        raise ApiError(
            status_code=404,
            code='collection_item_not_found',
            message='Collection item not found',
        )


@router.patch(
    '/collections/{collection_id}/items/{item_id}',
    response_model=CollectionItemReadResponse,
)
def update_collection_item(
    collection_id: UUID,
    item_id: UUID,
    request: SetCollectionItemFavoriteRequest,
    session: Session = Depends(get_db_session),
) -> CollectionItemReadResponse:
    collection_use_case = GetCollectionByIdUseCase(CollectionSqlRepository(session))
    if collection_use_case.execute(collection_id) is None:
        raise ApiError(status_code=404, code='collection_not_found', message='Collection not found')

    use_case = SetCollectionItemFavoriteUseCase(CollectionItemSqlRepository(session))
    updated_item = use_case.execute(
        collection_id=collection_id,
        item_id=item_id,
        is_favorite=request.is_favorite,
    )
    if updated_item is None:
        raise ApiError(
            status_code=404,
            code='collection_item_not_found',
            message='Collection item not found',
        )

    return CollectionItemReadResponse.from_domain(updated_item)


@router.post(
    '/collections/{collection_id}/generation-runs',
    response_model=GenerationRunSubmitResponse,
    status_code=202,
)
def create_generation_run(
    collection_id: UUID,
    request: GenerationRunSubmitRequest,
    settings: Settings = Depends(get_app_settings),
    session: Session = Depends(get_db_session),
    generation_provider: GenerationProviderPort = Depends(get_generation_provider),
    capability_registry: GenerationCapabilityRegistryPort = Depends(
        get_generation_capability_registry
    ),
    input_validator: GenerationInputValidator = Depends(get_generation_input_validator),
) -> GenerationRunSubmitResponse:
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

    use_case = SubmitGenerationRunUseCase(
        collection_item_repository=CollectionItemSqlRepository(session),
        generation_run_repository=GenerationRunSqlRepository(session),
        generation_provider=generation_provider,
        capability_registry=capability_registry,
        input_validator=input_validator,
        webhook_url=_build_generation_webhook_url(settings),
    )
    submission = use_case.execute(
        GenerationRunRequest(
            project_id=request.project_id,
            collection_id=collection_id,
            model_key=request.model_key,
            operation_key=request.operation_key,
            inputs=request.inputs,
            output_count=request.output_count,
            idempotency_key=request.idempotency_key,
        )
    )

    return GenerationRunSubmitResponse.from_domain(submission)


def _parse_upload_metadata(metadata_raw: str | None) -> JsonObject | None:
    if metadata_raw is None or len(metadata_raw.strip()) == 0:
        return None

    try:
        parsed = json.loads(metadata_raw)
    except json.JSONDecodeError as exc:
        raise ApiError(
            status_code=400,
            code='validation_error',
            message='Request validation failed',
            details={'errors': [{'loc': ['body', 'metadata'], 'msg': 'Invalid JSON payload'}]},
        ) from exc

    if not isinstance(parsed, dict):
        raise ApiError(
            status_code=400,
            code='validation_error',
            message='Request validation failed',
            details={'errors': [{'loc': ['body', 'metadata'], 'msg': 'Expected object'}]},
        )

    validated: JsonObject = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            raise ApiError(
                status_code=400,
                code='validation_error',
                message='Request validation failed',
                details={'errors': [{'loc': ['body', 'metadata'], 'msg': 'Expected string keys'}]},
            )
        validated[key] = value

    return validated


def _file_size(file: UploadFile) -> int:
    current = file.file.tell()
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(current, os.SEEK_SET)
    return size


def _build_generation_webhook_url(settings: Settings) -> str:
    base = settings.generation_webhook_public_base_url.rstrip('/')
    prefix = settings.api_v1_prefix
    if not prefix.startswith('/'):
        prefix = f'/{prefix}'
    return f'{base}{prefix}/provider-webhooks/fal?token={settings.generation_webhook_token}'
