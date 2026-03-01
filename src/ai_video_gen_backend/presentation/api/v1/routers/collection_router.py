from __future__ import annotations

import json
import os
from contextlib import suppress
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.collection import GetCollectionByIdUseCase
from ai_video_gen_backend.application.collection_item import (
    CreateCollectionItemUseCase,
    GenerateCollectionItemUseCase,
    GetCollectionItemsUseCase,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    UploadCollectionItemUseCase,
)
from ai_video_gen_backend.config.settings import Settings
from ai_video_gen_backend.domain.collection_item import (
    CollectionItemCreationPayload,
    CollectionItemGenerationParams,
    JsonObject,
    ObjectStoragePort,
    StorageError,
)
from ai_video_gen_backend.infrastructure.repositories import (
    CollectionItemSqlRepository,
    CollectionSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import (
    get_app_settings,
    get_db_session,
    get_object_storage,
)
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
    except UnsupportedMediaTypeError as exc:
        raise ApiError(
            status_code=400,
            code='unsupported_media_type',
            message='Only image/* and video/* uploads are allowed',
        ) from exc
    except PayloadTooLargeError as exc:
        raise ApiError(
            status_code=413,
            code='payload_too_large',
            message='Uploaded file exceeds max allowed size',
        ) from exc
    except StorageError as exc:
        raise ApiError(
            status_code=502,
            code='storage_upload_failed',
            message='Failed to upload object to storage',
        ) from exc
    except IntegrityError as exc:
        raise ApiError(
            status_code=400,
            code='constraint_violation',
            message='Invalid item payload for collection/project relationship',
            details={'reason': str(exc.__class__.__name__)},
        ) from exc
    finally:
        with suppress(Exception):
            file.file.close()

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
