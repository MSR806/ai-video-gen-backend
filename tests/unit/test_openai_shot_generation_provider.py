from __future__ import annotations

import pytest

from ai_video_gen_backend.domain.shot import ShotGenerationError
from ai_video_gen_backend.infrastructure.providers.openai_shot_generation_provider import (
    OpenAIShotGenerationProvider,
)


def test_generate_shots_returns_structured_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAIShotGenerationProvider(
        model_name='test-model',
        api_key='test-key',
        base_url='https://example.test/v1',
        temperature=0.1,
    )

    class FakeStructuredModel:
        def invoke(self, _messages: list[object]) -> object:
            return type(
                'Response',
                (),
                {
                    'shots': [
                        type(
                            'Shot',
                            (),
                            {
                                'title': 'Wide opener',
                                'description': 'Establishing skyline',
                                'camera_framing': 'Wide',
                                'camera_movement': 'Crane up',
                                'mood': 'Epic',
                            },
                        )()
                    ]
                },
            )()

    class FakeModel:
        def with_structured_output(self, _schema: object) -> FakeStructuredModel:
            return FakeStructuredModel()

    monkeypatch.setattr(provider, '_model', FakeModel())

    payload = provider.generate_shots('<scene><action>Generate</action></scene>')

    assert len(payload) == 1
    assert payload[0].title == 'Wide opener'
    assert payload[0].camera_movement == 'Crane up'


def test_generate_shots_raises_when_model_returns_invalid_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAIShotGenerationProvider(
        model_name='test-model',
        api_key='test-key',
        base_url='https://example.test/v1',
        temperature=0.1,
    )

    class FakeModel:
        def with_structured_output(self, _schema: object) -> object:
            class FakeStructuredModel:
                def invoke(self, _messages: list[object]) -> object:
                    raise ValueError('invalid structured payload')

            return FakeStructuredModel()

    monkeypatch.setattr(provider, '_model', FakeModel())

    with pytest.raises(ShotGenerationError, match='Failed to parse generated shots'):
        provider.generate_shots('<scene><action>Generate</action></scene>')


def test_generate_shots_raises_when_model_returns_empty_shots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAIShotGenerationProvider(
        model_name='test-model',
        api_key='test-key',
        base_url='https://example.test/v1',
        temperature=0.1,
    )

    class FakeStructuredModel:
        def invoke(self, _messages: list[object]) -> object:
            return type('Response', (), {'shots': []})()

    class FakeModel:
        def with_structured_output(self, _schema: object) -> FakeStructuredModel:
            return FakeStructuredModel()

    monkeypatch.setattr(provider, '_model', FakeModel())

    with pytest.raises(ShotGenerationError, match='returned no shots'):
        provider.generate_shots('<scene><action>Generate</action></scene>')
