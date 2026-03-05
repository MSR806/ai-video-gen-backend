from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from types import ModuleType
from typing import Literal

import fal_client
import httpx

from ai_video_gen_backend.domain.generation import (
    GeneratedOutput,
    GenerationProviderPort,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
)
from ai_video_gen_backend.domain.types import JsonObject

logger = logging.getLogger(__name__)


class FalGenerationProvider(GenerationProviderPort):
    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    def submit(
        self,
        *,
        endpoint_id: str,
        inputs: dict[str, object],
        webhook_url: str,
    ) -> ProviderSubmission:
        fal_client_module = self._client()
        logger.info(
            'Submitting generation request to FAL endpoint=%s payload=%s webhook_url=%s',
            endpoint_id,
            inputs,
            webhook_url,
        )
        handler = fal_client_module.submit(
            endpoint_id,
            arguments=inputs,
            webhook_url=webhook_url,
        )

        request_id = _extract_request_id(handler)
        if request_id is None:
            msg = 'fal submit response missing request_id'
            raise RuntimeError(msg)

        logger.info(
            'FAL generation request accepted endpoint=%s request_id=%s', endpoint_id, request_id
        )
        return ProviderSubmission(provider_request_id=request_id)

    def status(self, *, endpoint_id: str, provider_request_id: str) -> ProviderStatus:
        fal_client_module = self._client()
        status_response = fal_client_module.status(
            endpoint_id,
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
        endpoint_id: str,
        provider_request_id: str,
    ) -> ProviderResult:
        fal_client_module = self._client()
        response = fal_client_module.result(endpoint_id, provider_request_id)
        payload = _to_dict(response)
        resolved_payload = _resolve_result_payload(payload)
        outputs = _extract_outputs_from_payload(resolved_payload)

        if len(outputs) == 0:
            return ProviderResult(
                status='FAILED',
                outputs=[],
                raw_response=resolved_payload,
                error_message='No output URL in provider response',
            )

        return ProviderResult(
            status='SUCCEEDED',
            outputs=outputs,
            raw_response=resolved_payload,
        )

    def cancel(self, *, endpoint_id: str, provider_request_id: str) -> None:
        fal_client_module = self._client()
        fal_client_module.cancel(endpoint_id, provider_request_id)

    def parse_webhook(self, payload: dict[str, object]) -> ProviderWebhookEvent | None:
        request_id_raw = payload.get('request_id')
        if not isinstance(request_id_raw, str) or len(request_id_raw.strip()) == 0:
            return None

        status_raw = payload.get('status')
        if not isinstance(status_raw, str):
            return None

        normalized = status_raw.upper()
        outputs = _extract_outputs_from_payload(payload)

        if normalized in {'OK', 'COMPLETED', 'SUCCEEDED'}:
            return ProviderWebhookEvent(
                provider_request_id=request_id_raw,
                status='SUCCEEDED',
                outputs=outputs,
                raw_response=payload,
            )

        if normalized in {'ERROR', 'FAILED'}:
            error_message = payload.get('error')
            return ProviderWebhookEvent(
                provider_request_id=request_id_raw,
                status='FAILED',
                outputs=[],
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


def _resolve_result_payload(payload: dict[str, object]) -> dict[str, object]:
    if len(_extract_outputs_from_payload(payload)) > 0:
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


def _extract_outputs_from_payload(payload: dict[str, object]) -> list[GeneratedOutput]:
    candidates: list[dict[str, object]] = []
    nested_payload = payload.get('payload')
    if isinstance(nested_payload, dict):
        candidates.append(nested_payload)
    candidates.append(payload)

    extracted: list[GeneratedOutput] = []
    seen_urls: set[str] = set()

    for candidate in candidates:
        _append_outputs_from_key(
            extracted=extracted,
            seen_urls=seen_urls,
            candidate=candidate,
            key='images',
            media_type='image',
        )
        _append_outputs_from_key(
            extracted=extracted,
            seen_urls=seen_urls,
            candidate=candidate,
            key='videos',
            media_type='video',
        )
        _append_single_output(
            extracted=extracted,
            seen_urls=seen_urls,
            candidate=candidate,
            key='image',
            media_type='image',
        )
        _append_single_output(
            extracted=extracted,
            seen_urls=seen_urls,
            candidate=candidate,
            key='video',
            media_type='video',
        )

        generic_outputs = candidate.get('outputs')
        if isinstance(generic_outputs, list):
            for raw_output in generic_outputs:
                if not isinstance(raw_output, Mapping):
                    continue
                output_dict = _to_dict(raw_output)
                url = _extract_output_url(output_dict)
                if url is None or url in seen_urls:
                    continue
                seen_urls.add(url)
                media_type = _extract_output_media_type(output_dict)
                extracted.append(
                    GeneratedOutput(
                        index=len(extracted),
                        media_type=media_type,
                        provider_url=url,
                        metadata=_extract_metadata(output_dict),
                    )
                )

        output_url = candidate.get('output_url')
        if (
            isinstance(output_url, str)
            and len(output_url.strip()) > 0
            and output_url not in seen_urls
        ):
            seen_urls.add(output_url)
            extracted.append(
                GeneratedOutput(
                    index=len(extracted),
                    media_type='video',
                    provider_url=output_url,
                    metadata={},
                )
            )

    return extracted


def _append_outputs_from_key(
    *,
    extracted: list[GeneratedOutput],
    seen_urls: set[str],
    candidate: dict[str, object],
    key: str,
    media_type: Literal['image', 'video'],
) -> None:
    values = candidate.get(key)
    if not isinstance(values, list):
        return

    for raw_value in values:
        if not isinstance(raw_value, Mapping):
            continue
        output_dict = _to_dict(raw_value)
        url = _extract_output_url(output_dict)
        if url is None or url in seen_urls:
            continue
        seen_urls.add(url)
        extracted.append(
            GeneratedOutput(
                index=len(extracted),
                media_type=media_type,
                provider_url=url,
                metadata=_extract_metadata(output_dict),
            )
        )


def _append_single_output(
    *,
    extracted: list[GeneratedOutput],
    seen_urls: set[str],
    candidate: dict[str, object],
    key: str,
    media_type: Literal['image', 'video'],
) -> None:
    value = candidate.get(key)
    if not isinstance(value, Mapping):
        return
    output_dict = _to_dict(value)
    url = _extract_output_url(output_dict)
    if url is None or url in seen_urls:
        return
    seen_urls.add(url)
    extracted.append(
        GeneratedOutput(
            index=len(extracted),
            media_type=media_type,
            provider_url=url,
            metadata=_extract_metadata(output_dict),
        )
    )


def _extract_output_url(payload: dict[str, object]) -> str | None:
    url = payload.get('url')
    if isinstance(url, str) and len(url.strip()) > 0:
        return url

    provider_url = payload.get('provider_url')
    if isinstance(provider_url, str) and len(provider_url.strip()) > 0:
        return provider_url

    return None


def _extract_output_media_type(payload: dict[str, object]) -> Literal['image', 'video']:
    media_type = payload.get('media_type')
    if media_type == 'image':
        return 'image'
    if media_type == 'video':
        return 'video'

    content_type = payload.get('content_type')
    if isinstance(content_type, str):
        return 'video' if content_type.startswith('video/') else 'image'

    mime_type = payload.get('mime_type')
    if isinstance(mime_type, str):
        return 'video' if mime_type.startswith('video/') else 'image'

    return 'image'


def _extract_metadata(payload: dict[str, object]) -> JsonObject:
    metadata: JsonObject = {}
    for key, value in payload.items():
        if key in {'url', 'provider_url'}:
            continue
        metadata[key] = value
    return metadata
