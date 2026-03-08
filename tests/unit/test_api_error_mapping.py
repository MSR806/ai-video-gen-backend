from __future__ import annotations

import asyncio
import json
from typing import cast

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

from ai_video_gen_backend.application.generation import (
    GenerationFinalizationError,
    InvalidGenerationInputsError,
    ProviderSubmissionFailedError,
)
from ai_video_gen_backend.presentation.api.errors import (
    mapped_error_handler,
    validation_error_handler,
)


def _dummy_request() -> Request:
    return Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': []})


async def _json_response_payload(response: JSONResponse) -> dict[str, object]:
    raw_body = bytes(response.body)
    return cast(dict[str, object], json.loads(raw_body.decode('utf-8')))


def test_mapped_error_handler_maps_schema_validation_error_details() -> None:
    exc = InvalidGenerationInputsError(
        errors=[
            {
                'loc': ['body', 'inputs', 'prompt'],
                'msg': 'prompt is required',
            }
        ]
    )

    response = asyncio.run(mapped_error_handler(_dummy_request(), exc))
    payload = asyncio.run(_json_response_payload(response))

    assert response.status_code == 400
    assert payload == {
        'error': {
            'code': 'schema_validation_failed',
            'message': 'Generation inputs validation failed',
            'details': {
                'errors': [
                    {
                        'loc': ['body', 'inputs', 'prompt'],
                        'msg': 'prompt is required',
                    }
                ]
            },
        }
    }


def test_mapped_error_handler_maps_provider_failure_reason() -> None:
    exc = ProviderSubmissionFailedError(reason='TimeoutError')

    response = asyncio.run(mapped_error_handler(_dummy_request(), exc))
    payload = asyncio.run(_json_response_payload(response))

    assert response.status_code == 502
    assert payload == {
        'error': {
            'code': 'provider_submit_failed',
            'message': 'Failed to submit generation request',
            'details': {'reason': 'TimeoutError'},
        }
    }


def test_mapped_error_handler_uses_generation_finalize_message() -> None:
    exc = GenerationFinalizationError('thumbnail write failed')

    response = asyncio.run(mapped_error_handler(_dummy_request(), exc))
    payload = asyncio.run(_json_response_payload(response))

    assert response.status_code == 500
    assert payload == {
        'error': {
            'code': 'generation_finalize_failed',
            'message': 'thumbnail write failed',
        }
    }


def test_validation_error_handler_sanitizes_exception_objects() -> None:
    exc = RequestValidationError(
        [
            {
                'type': 'value_error',
                'loc': ('body', 'inputs', 'count'),
                'msg': 'invalid integer',
                'input': 'abc',
                'ctx': {'error': ValueError('bad int')},
            }
        ]
    )

    response = asyncio.run(validation_error_handler(_dummy_request(), exc))
    payload = asyncio.run(_json_response_payload(response))

    assert response.status_code == 422
    assert payload == {
        'error': {
            'code': 'validation_error',
            'message': 'Request validation failed',
            'details': {
                'errors': [
                    {
                        'type': 'value_error',
                        'loc': ['body', 'inputs', 'count'],
                        'msg': 'invalid integer',
                        'input': 'abc',
                        'ctx': {'error': 'bad int'},
                    }
                ]
            },
        }
    }
