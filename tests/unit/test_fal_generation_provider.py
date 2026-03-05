from __future__ import annotations

import os
from types import SimpleNamespace

import httpx
import pytest

from ai_video_gen_backend.infrastructure.providers.fal import (
    fal_generation_provider as provider_module,
)
from ai_video_gen_backend.infrastructure.providers.fal.fal_generation_provider import (
    FalGenerationProvider,
)


def test_extract_request_id_from_typed_handler_and_mapping() -> None:
    class TypedHandler:
        def __init__(self, request_id: str) -> None:
            self.request_id = request_id

    assert provider_module._extract_request_id(TypedHandler('req-typed')) == 'req-typed'
    assert provider_module._extract_request_id({'request_id': 'req-map'}) == 'req-map'
    assert provider_module._extract_request_id({'request_id': 123}) is None


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


def test_extract_status_uses_mapping_state_and_fallback() -> None:
    class UnknownStatus:
        pass

    assert provider_module._extract_status({'state': 'IN_PROGRESS'}) == 'IN_PROGRESS'
    assert provider_module._extract_status({'status': 'FAILED'}) == 'FAILED'
    assert provider_module._extract_status(UnknownStatus()) == 'ERROR'


@pytest.mark.parametrize(
    ('raw_status', 'expected'),
    [
        ('IN_QUEUE', 'IN_PROGRESS'),
        ('IN_PROGRESS', 'IN_PROGRESS'),
        ('COMPLETED', 'SUCCEEDED'),
        ('CANCELLED', 'CANCELLED'),
        ('CANCELED', 'CANCELLED'),
        ('FAILED', 'FAILED'),
        ('UNKNOWN', 'FAILED'),
    ],
)
def test_status_maps_provider_states(
    raw_status: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FalGenerationProvider(api_key='')
    fake_client = SimpleNamespace(
        status=lambda endpoint_id, provider_request_id, with_logs: {'status': raw_status}
    )
    monkeypatch.setattr(provider, '_client', lambda: fake_client)

    status = provider.status(endpoint_id='fal-ai/nano-banana', provider_request_id='req-1')

    assert status.status == expected


def test_submit_returns_submission_and_raises_on_missing_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FalGenerationProvider(api_key='')
    fake_client_ok = SimpleNamespace(
        submit=lambda endpoint_id, arguments, webhook_url: {'request_id': 'req-1'}
    )
    monkeypatch.setattr(provider, '_client', lambda: fake_client_ok)

    submission = provider.submit(
        endpoint_id='fal-ai/nano-banana',
        inputs={'prompt': 'cat'},
        webhook_url='https://backend.test/webhook',
    )

    assert submission.provider_request_id == 'req-1'

    fake_client_bad = SimpleNamespace(submit=lambda endpoint_id, arguments, webhook_url: {})
    monkeypatch.setattr(provider, '_client', lambda: fake_client_bad)

    with pytest.raises(RuntimeError, match='missing request_id'):
        provider.submit(
            endpoint_id='fal-ai/nano-banana',
            inputs={'prompt': 'cat'},
            webhook_url='https://backend.test/webhook',
        )


def test_result_reads_direct_outputs_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FalGenerationProvider(api_key='')
    fake_client = SimpleNamespace(
        result=lambda endpoint_id, provider_request_id: {
            'images': [{'url': 'https://v3b.fal.media/files/generated.png'}]
        }
    )
    monkeypatch.setattr(provider, '_client', lambda: fake_client)

    result = provider.result(endpoint_id='fal-ai/nano-banana', provider_request_id='req-123')

    assert result.status == 'SUCCEEDED'
    assert len(result.outputs) == 1
    assert result.outputs[0].provider_url == 'https://v3b.fal.media/files/generated.png'


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


def test_result_fails_when_no_output_anywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FalGenerationProvider(api_key='')
    fake_client = SimpleNamespace(
        result=lambda endpoint_id, provider_request_id: {'status': 'COMPLETED'}
    )
    monkeypatch.setattr(provider, '_client', lambda: fake_client)

    result = provider.result(endpoint_id='fal-ai/nano-banana', provider_request_id='req-789')

    assert result.status == 'FAILED'
    assert result.error_message == 'No output URL in provider response'


def test_parse_webhook_handles_success_failed_and_invalid_payloads() -> None:
    provider = FalGenerationProvider(api_key='')

    success_event = provider.parse_webhook(
        {
            'request_id': 'req-1',
            'status': 'OK',
            'images': [{'url': 'https://provider.test/image.png'}],
        }
    )
    assert success_event is not None
    assert success_event.status == 'SUCCEEDED'
    assert len(success_event.outputs) == 1

    failed_event = provider.parse_webhook(
        {
            'request_id': 'req-2',
            'status': 'FAILED',
            'error': 'quota exceeded',
        }
    )
    assert failed_event is not None
    assert failed_event.status == 'FAILED'
    assert failed_event.error_message == 'quota exceeded'

    assert provider.parse_webhook({'status': 'FAILED'}) is None
    assert provider.parse_webhook({'request_id': 'req-3', 'status': 'PENDING'}) is None


def test_extract_response_url_supports_nested_and_camel_case() -> None:
    assert (
        provider_module._extract_response_url(
            {'payload': {'response_url': 'https://queue.fal.run/response'}}
        )
        == 'https://queue.fal.run/response'
    )
    assert (
        provider_module._extract_response_url({'responseUrl': 'https://queue.fal.run/camel'})
        == 'https://queue.fal.run/camel'
    )
    assert provider_module._extract_response_url({'status': 'ok'}) is None


def test_to_dict_handles_mapping_data_attribute_and_raw() -> None:
    class WithData:
        def __init__(self, data: dict[str, object]) -> None:
            self.data = data

    class RawValue:
        pass

    assert provider_module._to_dict({'k': 'v'}) == {'k': 'v'}
    assert provider_module._to_dict(WithData({'x': 1})) == {'x': 1}
    raw = RawValue()
    assert provider_module._to_dict(raw) == {'raw': raw}


def test_extract_outputs_from_payload_handles_multiple_shapes_and_deduplicates() -> None:
    payload: dict[str, object] = {
        'images': [{'url': 'https://provider.test/image-1.png'}],
        'videos': [{'url': 'https://provider.test/video-1.mp4'}],
        'image': {'url': 'https://provider.test/image-2.png'},
        'video': {'url': 'https://provider.test/video-2.mp4'},
        'outputs': [
            {'provider_url': 'https://provider.test/image-2.png', 'media_type': 'image'},
            {'url': 'https://provider.test/image-3.png', 'content_type': 'image/png'},
            {'url': 'https://provider.test/video-3.mp4', 'mime_type': 'video/mp4'},
        ],
        'output_url': 'https://provider.test/video-final.mp4',
    }

    outputs = provider_module._extract_outputs_from_payload(payload)

    assert [output.provider_url for output in outputs] == [
        'https://provider.test/image-1.png',
        'https://provider.test/video-1.mp4',
        'https://provider.test/image-2.png',
        'https://provider.test/video-2.mp4',
        'https://provider.test/image-3.png',
        'https://provider.test/video-3.mp4',
        'https://provider.test/video-final.mp4',
    ]
    assert outputs[1].media_type == 'video'
    assert outputs[4].media_type == 'image'
    assert outputs[5].media_type == 'video'


def test_extract_output_media_type_and_metadata_helpers() -> None:
    assert provider_module._extract_output_media_type({'media_type': 'image'}) == 'image'
    assert provider_module._extract_output_media_type({'media_type': 'video'}) == 'video'
    assert provider_module._extract_output_media_type({'content_type': 'video/mp4'}) == 'video'
    assert provider_module._extract_output_media_type({'mime_type': 'video/mp4'}) == 'video'
    assert provider_module._extract_output_media_type({}) == 'image'

    metadata = provider_module._extract_metadata(
        {'url': 'https://provider.test/file.png', 'provider_url': 'x', 'seed': 42}
    )
    assert metadata == {'seed': 42}


def test_fetch_response_payload_success_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __init__(
            self, *, data: dict[str, object] | None = None, bad_json: bool = False
        ) -> None:
            self._data = data or {}
            self._bad_json = bad_json

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            if self._bad_json:
                raise ValueError('bad json')
            return self._data

    class FakeClient:
        def __init__(
            self, *, response: FakeResponse | None = None, error: Exception | None = None
        ) -> None:
            self._response = response
            self._error = error

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            del exc_type, exc, tb

        def get(self, url: str) -> FakeResponse:
            del url
            if self._error is not None:
                raise self._error
            assert self._response is not None
            return self._response

    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.providers.fal.fal_generation_provider.httpx.Client',
        lambda timeout, follow_redirects: FakeClient(response=FakeResponse(data={'images': []})),
    )
    assert provider_module._fetch_response_payload('https://queue.fal.run/ok') == {'images': []}

    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.providers.fal.fal_generation_provider.httpx.Client',
        lambda timeout, follow_redirects: FakeClient(error=httpx.HTTPError('boom')),
    )
    assert provider_module._fetch_response_payload('https://queue.fal.run/error') is None

    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.providers.fal.fal_generation_provider.httpx.Client',
        lambda timeout, follow_redirects: FakeClient(response=FakeResponse(bad_json=True)),
    )
    assert provider_module._fetch_response_payload('https://queue.fal.run/bad-json') is None


def test_cancel_delegates_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    provider = FalGenerationProvider(api_key='')
    fake_client = SimpleNamespace(
        cancel=lambda endpoint_id, provider_request_id: calls.append(
            (endpoint_id, provider_request_id)
        )
    )
    monkeypatch.setattr(provider, '_client', lambda: fake_client)

    provider.cancel(endpoint_id='fal-ai/nano-banana', provider_request_id='req-cancel')

    assert calls == [('fal-ai/nano-banana', 'req-cancel')]


def test_client_sets_fal_key_when_api_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FalGenerationProvider(api_key='secret-key')
    monkeypatch.delenv('FAL_KEY', raising=False)

    client = provider._client()

    assert os.environ['FAL_KEY'] == 'secret-key'
    assert hasattr(client, 'submit')
