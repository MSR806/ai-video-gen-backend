from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_video_gen_backend.infrastructure.providers.fal import (
    fal_generation_provider as provider_module,
)
from ai_video_gen_backend.infrastructure.providers.fal.fal_generation_provider import (
    FalGenerationProvider,
)


def test_extract_status_handles_typed_completed_object() -> None:
    class Completed:
        def __init__(self) -> None:
            self.logs = None
            self.metrics = {'inference_time': 1.23}

    assert provider_module._extract_status(Completed()) == 'COMPLETED'


def test_extract_status_handles_typed_in_progress_object() -> None:
    class InProgress:
        def __init__(self) -> None:
            self.logs = None
            self.metrics = None

    assert provider_module._extract_status(InProgress()) == 'IN_PROGRESS'


def test_result_uses_response_url_payload_when_envelope_has_no_direct_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FalGenerationProvider(api_key='')
    fake_client = SimpleNamespace(
        result=lambda endpoint_id, provider_request_id: {
            'status': 'COMPLETED',
            'request_id': provider_request_id,
            'response_url': f'https://queue.fal.run/{endpoint_id}/requests/{provider_request_id}',
        }
    )
    monkeypatch.setattr(provider, '_client', lambda: fake_client)
    monkeypatch.setattr(
        provider_module,
        '_fetch_response_payload',
        lambda response_url: {
            'images': [{'url': 'https://v3b.fal.media/files/generated.png'}],
            'response_url': response_url,
        },
    )

    result = provider.result(
        endpoint_id='fal-ai/nano-banana',
        provider_request_id='req-123',
    )

    assert result.status == 'SUCCEEDED'
    assert len(result.outputs) == 1
    assert result.outputs[0].provider_url == 'https://v3b.fal.media/files/generated.png'
    assert result.outputs[0].media_type == 'image'


def test_result_fails_when_response_url_payload_has_no_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FalGenerationProvider(api_key='')
    fake_client = SimpleNamespace(
        result=lambda endpoint_id, provider_request_id: {
            'status': 'COMPLETED',
            'request_id': provider_request_id,
            'response_url': f'https://queue.fal.run/{endpoint_id}/requests/{provider_request_id}',
        }
    )
    monkeypatch.setattr(provider, '_client', lambda: fake_client)
    monkeypatch.setattr(
        provider_module,
        '_fetch_response_payload',
        lambda _response_url: {'description': 'no image'},
    )

    result = provider.result(
        endpoint_id='fal-ai/nano-banana',
        provider_request_id='req-456',
    )

    assert result.status == 'FAILED'
    assert result.outputs == []
    assert result.error_message == 'No output URL in provider response'
