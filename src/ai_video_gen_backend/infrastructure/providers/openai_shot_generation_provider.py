from __future__ import annotations

from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_video_gen_backend.domain.shot import ShotCreateInput, ShotGenerationError

_SHOT_GENERATION_SYSTEM_PROMPT = (
    'You are a film storyboard assistant. Return a structured response with a shots array. '
    'Each shots item must include string fields: '
    'title, description, camera_framing, camera_movement, mood. '
    'Generate a natural number of shots based on scene complexity.'
)


class OpenAIShotGenerationProvider:
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

    def generate_shots(self, scene_content: str) -> list[ShotCreateInput]:
        structured_model = self._model.with_structured_output(_ShotListResponse)
        try:
            response = cast(
                _ShotListResponse,
                structured_model.invoke(
                    [
                        SystemMessage(content=_SHOT_GENERATION_SYSTEM_PROMPT),
                        HumanMessage(content=scene_content),
                    ]
                ),
            )
        except Exception as exc:
            raise ShotGenerationError(f'Failed to parse generated shots: {exc}') from exc

        shots = response.shots
        if len(shots) == 0:
            raise ShotGenerationError('Shot generator returned no shots')

        return [
            ShotCreateInput(
                title=shot.title,
                description=shot.description,
                camera_framing=shot.camera_framing,
                camera_movement=shot.camera_movement,
                mood=shot.mood,
            )
            for shot in shots
        ]


class _ShotSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')

    title: str
    description: str
    camera_framing: str
    camera_movement: str
    mood: str

    @field_validator('title', 'description', 'camera_framing', 'camera_movement', 'mood')
    @classmethod
    def _validate_non_empty_string(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('must not be empty')
        return normalized


class _ShotListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    shots: list[_ShotSchema] = Field(
        description='Generated storyboard shots for the scene.',
    )
