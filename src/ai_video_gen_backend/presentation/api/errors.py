from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception('Unhandled server error: %s', exc)
    return _error_response(
        status_code=500,
        code='internal_server_error',
        message='Internal server error',
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
