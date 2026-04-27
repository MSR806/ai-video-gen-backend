from __future__ import annotations

import json
from collections.abc import Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ai_video_gen_backend.domain.shot import ShotCreateInput, ShotGenerationError

_SHOT_GENERATION_SYSTEM_PROMPT = (
    'You are a film storyboard assistant. Return only a JSON array (no markdown, no prose). '
    'Each array item must be an object with string fields: '
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
        response = self._model.invoke(
            [
                SystemMessage(content=_SHOT_GENERATION_SYSTEM_PROMPT),
                HumanMessage(content=scene_content),
            ]
        )
        rendered = _extract_text(response.content)
        return _parse_shot_payloads(rendered)


def _extract_text(content: object) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, Sequence):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue

            if isinstance(item, dict):
                text_value = item.get('text')
                if isinstance(text_value, str):
                    chunks.append(text_value)

        combined = '\n'.join(chunk for chunk in chunks if chunk)
        if combined:
            return combined

    raise ShotGenerationError('Model returned no text content')


def _parse_shot_payloads(raw_text: str) -> list[ShotCreateInput]:
    payload = _load_shot_json(raw_text)
    if not isinstance(payload, list):
        raise ShotGenerationError('Shot generator response must be a JSON array')
    if len(payload) == 0:
        raise ShotGenerationError('Shot generator returned no shots')

    parsed: list[ShotCreateInput] = []
    for item in payload:
        parsed.append(_parse_shot_item(item))
    return parsed


def _load_shot_json(raw_text: str) -> object:
    text = raw_text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('[')
        end = text.rfind(']')
        if start == -1 or end == -1 or end <= start:
            raise ShotGenerationError('Shot generator response is not valid JSON') from None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ShotGenerationError('Shot generator response is not valid JSON') from exc


def _parse_shot_item(item: object) -> ShotCreateInput:
    if not isinstance(item, dict):
        raise ShotGenerationError('Each generated shot must be an object')

    title = _read_required_string(item, 'title')
    description = _read_required_string(item, 'description')
    camera_framing = _read_required_string(item, 'camera_framing')
    camera_movement = _read_required_string(item, 'camera_movement')
    mood = _read_required_string(item, 'mood')

    return ShotCreateInput(
        title=title,
        description=description,
        camera_framing=camera_framing,
        camera_movement=camera_movement,
        mood=mood,
    )


def _read_required_string(item: dict[object, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str):
        raise ShotGenerationError(f'Generated shot field {key} must be a string')

    normalized = value.strip()
    if not normalized:
        raise ShotGenerationError(f'Generated shot field {key} must not be empty')

    return normalized
