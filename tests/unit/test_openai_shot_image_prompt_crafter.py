from __future__ import annotations

import pytest

from ai_video_gen_backend.domain.shot import ShotImagePromptCraftRequest
from ai_video_gen_backend.infrastructure.providers.openai_shot_image_prompt_crafter import (
    OpenAIShotImagePromptCrafter,
)


def test_craft_prompt_returns_structured_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAIShotImagePromptCrafter(
        model_name='test-model',
        api_key='test-key',
        base_url='https://example.test/v1',
        temperature=0.1,
    )

    class FakeStructuredModel:
        def invoke(self, _messages: list[object]) -> object:
            return type('Response', (), {'prompt': 'cinematic rain-soaked alley, dolly in'})()

    class FakeModel:
        def with_structured_output(self, _schema: object) -> FakeStructuredModel:
            return FakeStructuredModel()

    monkeypatch.setattr(provider, '_model', FakeModel())

    result = provider.craft_prompt(
        ShotImagePromptCraftRequest(
            project_name='Night Drive',
            project_style='neo-noir 35mm grain',
            shot_title='Hero reveal',
            shot_description='Character exits car',
            camera_framing='Medium close-up',
            camera_movement='Slow dolly in',
            mood='Tense',
            scene_context='Rain, neon reflections, distant sirens.',
        )
    )

    assert result.prompt == 'cinematic rain-soaked alley, dolly in'
