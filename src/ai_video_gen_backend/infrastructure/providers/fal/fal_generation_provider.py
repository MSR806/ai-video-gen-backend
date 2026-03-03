from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from types import ModuleType

import fal_client
import httpx

from ai_video_gen_backend.domain.generation import (
    GenerationOperation,
    GenerationProviderPort,
    GenerationRequest,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
)
from ai_video_gen_backend.infrastructure.providers.fal.model_catalog import (
    get_model_profile,
    resolve_model_key,
)
from ai_video_gen_backend.infrastructure.providers.fal.model_mapper_registry import (
    get_model_mapper,
)

logger = logging.getLogger(__name__)


class FalGenerationProvider(GenerationProviderPort):
    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    def resolve_model_key(self, *, operation: GenerationOperation, model_key: str | None) -> str:
        return resolve_model_key(operation=operation, model_key=model_key)

    def submit(self, request: GenerationRequest, *, webhook_url: str) -> ProviderSubmission:
        fal_client = self._client()
        profile = get_model_profile(request.model_key or '')
        mapper = get_model_mapper(profile.mapper_key)
        arguments = mapper.to_arguments(request)
        logger.info(
            'Submitting generation request to FAL '
            'endpoint=%s model_key=%s payload=%s webhook_url=%s',
            profile.endpoint_id,
            profile.key,
            arguments,
            webhook_url,
        )
        handler = fal_client.submit(
            profile.endpoint_id,
            arguments=arguments,
            webhook_url=webhook_url,
        )

        request_id = _extract_request_id(handler)
        if request_id is None:
            msg = 'fal submit response missing request_id'
            raise RuntimeError(msg)

        logger.info(
            'FAL generation request accepted endpoint=%s model_key=%s request_id=%s',
            profile.endpoint_id,
            profile.key,
            request_id,
        )

        return ProviderSubmission(provider_request_id=request_id)

    def status(self, *, model_key: str, provider_request_id: str) -> ProviderStatus:
        fal_client = self._client()
        profile = get_model_profile(model_key)
        status_response = fal_client.status(
            profile.endpoint_id,
            provider_request_id,
            with_logs=False,
        )
        raw_status = _extract_status(status_response)

        if raw_status in {'IN_QUEUE', 'IN_PROGRESS'}:
            return ProviderStatus(status='IN_PROGRESS')
        if raw_status == 'COMPLETED':
            return ProviderStatus(status='SUCCEEDED')
        if raw_status in {'CANCELLED', 'CANCELED'}:
            return ProviderStatus(status='CANCELLED')
        return ProviderStatus(status='FAILED')

    def result(
        self,
        *,
        model_key: str,
        provider_request_id: str,
    ) -> ProviderResult:
        fal_client = self._client()
        profile = get_model_profile(model_key)
        mapper = get_model_mapper(profile.mapper_key)
        response = fal_client.result(profile.endpoint_id, provider_request_id)
        payload = _to_dict(response)
        resolved_payload = _resolve_result_payload(payload)
        output_url = mapper.extract_output_url(resolved_payload)
        if output_url is None:
            output_url = _extract_output_url_from_payload(resolved_payload)
        if output_url is None:
            return ProviderResult(
                status='FAILED',
                output_url=None,
                raw_response=resolved_payload,
                error_message='No output URL in provider response',
            )

        return ProviderResult(
            status='SUCCEEDED',
            output_url=output_url,
            raw_response=resolved_payload,
        )

    def cancel(self, *, model_key: str, provider_request_id: str) -> None:
        fal_client = self._client()
        profile = get_model_profile(model_key)
        fal_client.cancel(profile.endpoint_id, provider_request_id)

    def parse_webhook(self, payload: dict[str, object]) -> ProviderWebhookEvent | None:
        request_id_raw = payload.get('request_id')
        if not isinstance(request_id_raw, str) or len(request_id_raw.strip()) == 0:
            return None

        status_raw = payload.get('status')
        if not isinstance(status_raw, str):
            return None

        normalized = status_raw.upper()
        output_url = _extract_output_url_from_payload(payload)

        if normalized in {'OK', 'COMPLETED', 'SUCCEEDED'}:
            return ProviderWebhookEvent(
                provider_request_id=request_id_raw,
                status='SUCCEEDED',
                output_url=output_url,
                raw_response=payload,
            )

        if normalized in {'ERROR', 'FAILED'}:
            error_message = payload.get('error')
            return ProviderWebhookEvent(
                provider_request_id=request_id_raw,
                status='FAILED',
                output_url=None,
                raw_response=payload,
                error_message=error_message if isinstance(error_message, str) else None,
            )

        return None

    def _client(self) -> ModuleType:
        if len(self._api_key.strip()) > 0:
            os.environ['FAL_KEY'] = self._api_key
        return fal_client


def _extract_request_id(handler: object) -> str | None:
    try:
        request_id = handler.request_id  # type: ignore[attr-defined]
        if isinstance(request_id, str):
            return request_id
    except AttributeError:
        pass

    if isinstance(handler, Mapping):
        request_id = handler.get('request_id')
        if isinstance(request_id, str):
            return request_id

    return None


def _extract_status(status_response: object) -> str:
    try:
        status_value = status_response.status  # type: ignore[attr-defined]
        if isinstance(status_value, str):
            return status_value
    except AttributeError:
        pass

    if isinstance(status_response, Mapping):
        status_value = status_response.get('status')
        if isinstance(status_value, str):
            return status_value
        state_value = status_response.get('state')
        if isinstance(state_value, str):
            return state_value

    # fal-client may return typed status objects like Completed(logs=..., metrics=...)
    # without a `status` attribute. Fall back to class-name normalization.
    class_name = type(status_response).__name__
    if len(class_name) > 0:
        normalized = re.sub(r'(?<!^)([A-Z])', r'_\1', class_name).upper()
        if normalized in {
            'IN_QUEUE',
            'IN_PROGRESS',
            'COMPLETED',
            'CANCELLED',
            'CANCELED',
            'FAILED',
        }:
            return normalized

    return 'ERROR'


def _to_dict(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}

    try:
        data_value = value.data  # type: ignore[attr-defined]
        if isinstance(data_value, Mapping):
            return {str(k): v for k, v in data_value.items()}
    except AttributeError:
        pass

    return {'raw': value}


def _extract_output_url_from_payload(payload: dict[str, object]) -> str | None:
    candidates: list[dict[str, object]] = []
    nested_payload = payload.get('payload')
    if isinstance(nested_payload, dict):
        candidates.append(nested_payload)
    candidates.append(payload)

    for candidate in candidates:
        images = candidate.get('images')
        if isinstance(images, list) and len(images) > 0:
            first = images[0]
            if isinstance(first, dict):
                url = first.get('url')
                if isinstance(url, str) and len(url.strip()) > 0:
                    return url

    return None


def _resolve_result_payload(payload: dict[str, object]) -> dict[str, object]:
    if _extract_output_url_from_payload(payload) is not None:
        return payload

    response_url = _extract_response_url(payload)
    if response_url is None:
        return payload

    response_payload = _fetch_response_payload(response_url)
    if response_payload is None:
        return payload

    return response_payload


def _extract_response_url(payload: dict[str, object]) -> str | None:
    candidates: list[dict[str, object]] = []
    nested_payload = payload.get('payload')
    if isinstance(nested_payload, dict):
        candidates.append(nested_payload)
    candidates.append(payload)

    for candidate in candidates:
        response_url = candidate.get('response_url')
        if isinstance(response_url, str) and len(response_url.strip()) > 0:
            return response_url.strip()
        response_url_camel = candidate.get('responseUrl')
        if isinstance(response_url_camel, str) and len(response_url_camel.strip()) > 0:
            return response_url_camel.strip()

    return None


def _fetch_response_payload(response_url: str) -> dict[str, object] | None:
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(response_url)
            response.raise_for_status()
            parsed = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    return _to_dict(parsed)
