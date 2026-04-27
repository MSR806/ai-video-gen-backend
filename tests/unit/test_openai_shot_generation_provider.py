from __future__ import annotations

import pytest

from ai_video_gen_backend.domain.shot import ShotGenerationError
from ai_video_gen_backend.infrastructure.providers.openai_shot_generation_provider import (
    OpenAIShotGenerationProvider,
    _parse_shot_payloads,
)


def test_parse_shot_payloads_accepts_wrapped_json_array() -> None:
    payload = _parse_shot_payloads(
        'Sure, here it is:\n'
        '[{"title":"Wide opener","description":"Establishing skyline",'
        '"camera_framing":"Wide","camera_movement":"Crane up","mood":"Epic"}]'
    )

    assert len(payload) == 1
    assert payload[0].title == 'Wide opener'
    assert payload[0].camera_movement == 'Crane up'


def test_parse_shot_payloads_rejects_empty_array() -> None:
    with pytest.raises(ShotGenerationError, match='returned no shots'):
        _parse_shot_payloads('[]')


def test_generate_shots_raises_when_model_returns_invalid_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAIShotGenerationProvider(
        model_name='test-model',
        api_key='test-key',
        base_url='https://example.test/v1',
        temperature=0.1,
    )

    class FakeResponse:
        def __init__(self, content: object) -> None:
            self.content = content

    class FakeModel:
        def invoke(self, _messages: list[object]) -> FakeResponse:
            return FakeResponse('{"not":"an array"}')

    monkeypatch.setattr(provider, '_model', FakeModel())

    with pytest.raises(ShotGenerationError, match='JSON array'):
        provider.generate_shots('<scene><action>Generate</action></scene>')
