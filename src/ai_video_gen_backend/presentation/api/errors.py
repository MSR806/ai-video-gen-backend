from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ai_video_gen_backend.application.collection_item import (
    DeleteStorageFailureError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    UploadStorageFailureError,
)
from ai_video_gen_backend.application.generation import (
    GenerationCapabilitiesLoadError,
    GenerationFinalizationError,
    GenerationModelRegistryLoadError,
    InvalidGenerationInputsError,
    InvalidOutputCountError,
    ProviderSubmissionFailedError,
    UnsupportedBatchOutputCountError,
    UnsupportedModelKeyError,
    UnsupportedOperationKeyError,
)
from ai_video_gen_backend.application.shot import (
    InvalidShotGenerationError,
    ProjectNotFoundError,
    ScreenplaySceneNotFoundError,
    ShotNotFoundError,
)
from ai_video_gen_backend.domain.collection_item import (
    CollectionItemConstraintViolationError,
)

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


MessageFactory = Callable[[Exception], str]
DetailsFactory = Callable[[Exception], dict[str, object] | None]


@dataclass(frozen=True, slots=True)
class _ApiExceptionMapping:
    status_code: int
    code: str
    message: str | MessageFactory
    details_factory: DetailsFactory | None = None


def _constraint_violation_details(exc: Exception) -> dict[str, object]:
    reason_source = exc.__cause__ if exc.__cause__ is not None else exc
    return {'reason': reason_source.__class__.__name__}


def _schema_validation_details(exc: Exception) -> dict[str, object] | None:
    if isinstance(exc, InvalidGenerationInputsError):
        return {'errors': exc.errors}
    return None


def _provider_submit_details(exc: Exception) -> dict[str, object] | None:
    if isinstance(exc, ProviderSubmissionFailedError):
        return {'reason': exc.reason}
    return None


def _generation_finalize_message(exc: Exception) -> str:
    return str(exc)


_API_EXCEPTION_MAPPINGS: tuple[tuple[type[Exception], _ApiExceptionMapping], ...] = (
    (
        CollectionItemConstraintViolationError,
        _ApiExceptionMapping(
            status_code=400,
            code='constraint_violation',
            message='Invalid item payload for collection/project relationship',
            details_factory=_constraint_violation_details,
        ),
    ),
    (
        UnsupportedMediaTypeError,
        _ApiExceptionMapping(
            status_code=400,
            code='unsupported_media_type',
            message='Only image/* and video/* uploads are allowed',
        ),
    ),
    (
        PayloadTooLargeError,
        _ApiExceptionMapping(
            status_code=413,
            code='payload_too_large',
            message='Uploaded file exceeds max allowed size',
        ),
    ),
    (
        UploadStorageFailureError,
        _ApiExceptionMapping(
            status_code=502,
            code='storage_upload_failed',
            message='Failed to upload object to storage',
        ),
    ),
    (
        DeleteStorageFailureError,
        _ApiExceptionMapping(
            status_code=502,
            code='storage_delete_failed',
            message='Failed to delete object from storage',
        ),
    ),
    (
        UnsupportedModelKeyError,
        _ApiExceptionMapping(
            status_code=400,
            code='unsupported_model_key',
            message='Unsupported or disabled model key',
        ),
    ),
    (
        UnsupportedOperationKeyError,
        _ApiExceptionMapping(
            status_code=400,
            code='unsupported_operation_key',
            message='Unsupported operation key for model',
        ),
    ),
    (
        InvalidOutputCountError,
        _ApiExceptionMapping(
            status_code=400,
            code='invalid_output_count',
            message='Output count must be between 1 and 4',
        ),
    ),
    (
        UnsupportedBatchOutputCountError,
        _ApiExceptionMapping(
            status_code=400,
            code='unsupported_batch_output_count',
            message='Selected model operation does not support multi-output generation',
        ),
    ),
    (
        InvalidGenerationInputsError,
        _ApiExceptionMapping(
            status_code=400,
            code='schema_validation_failed',
            message='Generation inputs validation failed',
            details_factory=_schema_validation_details,
        ),
    ),
    (
        GenerationCapabilitiesLoadError,
        _ApiExceptionMapping(
            status_code=500,
            code='capability_registry_load_failed',
            message='Failed to load generation capabilities',
        ),
    ),
    (
        GenerationModelRegistryLoadError,
        _ApiExceptionMapping(
            status_code=500,
            code='capability_registry_load_failed',
            message='Failed to load generation model registry',
        ),
    ),
    (
        ProviderSubmissionFailedError,
        _ApiExceptionMapping(
            status_code=502,
            code='provider_submit_failed',
            message='Failed to submit generation request',
            details_factory=_provider_submit_details,
        ),
    ),
    (
        GenerationFinalizationError,
        _ApiExceptionMapping(
            status_code=500,
            code='generation_finalize_failed',
            message=_generation_finalize_message,
        ),
    ),
    (
        InvalidShotGenerationError,
        _ApiExceptionMapping(
            status_code=400,
            code='invalid_shot_generation',
            message='Generated shots response is invalid',
        ),
    ),
    (
        ProjectNotFoundError,
        _ApiExceptionMapping(
            status_code=404,
            code='project_not_found',
            message='Project not found',
        ),
    ),
    (
        ScreenplaySceneNotFoundError,
        _ApiExceptionMapping(
            status_code=404,
            code='screenplay_scene_not_found',
            message='Screenplay scene not found',
        ),
    ),
    (
        ShotNotFoundError,
        _ApiExceptionMapping(
            status_code=404,
            code='shot_not_found',
            message='Shot not found',
        ),
    ),
)


def _map_to_api_error(exc: Exception) -> ApiError | None:
    for exception_type, mapping in _API_EXCEPTION_MAPPINGS:
        if isinstance(exc, exception_type):
            message = mapping.message if isinstance(mapping.message, str) else mapping.message(exc)
            details = None if mapping.details_factory is None else mapping.details_factory(exc)
            return ApiError(
                status_code=mapping.status_code,
                code=mapping.code,
                message=message,
                details=details,
            )
    return None


def _sanitize_validation_error(value: object) -> object:
    if isinstance(value, dict):
        return {key: _sanitize_validation_error(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_sanitize_validation_error(item) for item in value]

    if isinstance(value, tuple):
        return [_sanitize_validation_error(item) for item in value]

    if isinstance(value, Exception):
        return str(value)

    return value


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    payload: dict[str, object] = {'error': {'code': code, 'message': message}}
    if details is not None:
        payload['error'] = {'code': code, 'message': message, 'details': details}
    return JSONResponse(status_code=status_code, content=payload)


async def api_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):
        return _error_response(
            status_code=500,
            code='internal_server_error',
            message='Internal server error',
        )

    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return _error_response(
            status_code=500,
            code='internal_server_error',
            message='Internal server error',
        )

    return _error_response(
        status_code=422,
        code='validation_error',
        message='Request validation failed',
        details={'errors': _sanitize_validation_error(exc.errors())},
    )


async def mapped_error_handler(_: Request, exc: Exception) -> JSONResponse:
    mapped_api_error = _map_to_api_error(exc)
    if mapped_api_error is None:
        logger.exception('Unhandled mapped error: %s', exc)
        return _error_response(
            status_code=500,
            code='internal_server_error',
            message='Internal server error',
        )

    return _error_response(
        status_code=mapped_api_error.status_code,
        code=mapped_api_error.code,
        message=mapped_api_error.message,
        details=mapped_api_error.details,
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception('Unhandled server error: %s', exc)
    return _error_response(
        status_code=500,
        code='internal_server_error',
        message='Internal server error',
    )


def register_exception_handlers(app: FastAPI) -> None:
    for exception_type, _ in _API_EXCEPTION_MAPPINGS:
        app.add_exception_handler(exception_type, mapped_error_handler)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
