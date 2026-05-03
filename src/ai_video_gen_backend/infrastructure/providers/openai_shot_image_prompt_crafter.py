from __future__ import annotations

from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, field_validator

from ai_video_gen_backend.domain.shot import (
    ShotImagePromptCraftRequest,
    ShotImagePromptCraftResult,
)

_SYSTEM_PROMPT = (
    'You craft concise, production-ready image-generation prompts for a single film shot. '
    'Integrate shot details naturally into one coherent prompt, not a field-by-field list. '
    'Use scene context only as secondary enrichment. '
    'Keep it focused and avoid over-weighting scene details. '
    'If project style is missing, do not invent one. Return plain prompt text only.'
)


class OpenAIShotImagePromptCrafter:
    def __init__(
        self,
        *,
        model_name: str,
        api_key: str,
        base_url: str | None,
        temperature: float,
    ) -> None:
        self._model = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
        )

    def craft_prompt(self, request: ShotImagePromptCraftRequest) -> ShotImagePromptCraftResult:
        structured_model = self._model.with_structured_output(_PromptResponse)
        style_value = request.project_style.strip() if request.project_style is not None else ''
        style_line = style_value if style_value else '(none)'
        user_input = (
            f'Project: {request.project_name}\n'
            f'Project style: {style_line}\n'
            f'Shot title: {request.shot_title}\n'
            f'Shot description: {request.shot_description}\n'
            f'Camera framing: {request.camera_framing}\n'
            f'Camera movement: {request.camera_movement}\n'
            f'Mood: {request.mood}\n'
            f'Scene context (secondary): {request.scene_context}'
        )
        response = cast(
            _PromptResponse,
            structured_model.invoke(
                [
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HumanMessage(content=user_input),
                ]
            ),
        )
        return ShotImagePromptCraftResult(prompt=response.prompt)


class _PromptResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    prompt: str

    @field_validator('prompt')
    @classmethod
    def _validate_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) == 0:
            raise ValueError('prompt must not be empty')
        return normalized
