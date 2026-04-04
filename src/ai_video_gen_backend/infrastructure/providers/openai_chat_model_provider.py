from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, TypedDict, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from ai_video_gen_backend.domain.chat import ChatMessage


class _TextContentPart(TypedDict):
    type: Literal['text']
    text: str


class _ImageUrlValue(TypedDict):
    url: str


class _ImageUrlContentPart(TypedDict):
    type: Literal['image_url']
    image_url: _ImageUrlValue


_HumanContentPart = _TextContentPart | _ImageUrlContentPart


class OpenAIChatModelProvider:
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

    def generate_reply(self, *, messages: list[ChatMessage]) -> str:
        lc_messages = [_to_langchain_message(message) for message in messages]
        response = self._model.invoke(lc_messages)
        return _extract_text(response.content)

    def as_langchain_chat_model(self) -> object:
        return self._model


def _to_langchain_message(message: ChatMessage) -> BaseMessage:
    if message.role == 'assistant':
        return AIMessage(content=_render_text_with_image_urls(message))

    if not message.images:
        return HumanMessage(content=message.text)

    parts: list[_HumanContentPart] = []
    if message.text:
        parts.append({'type': 'text', 'text': message.text})
    parts.extend({'type': 'image_url', 'image_url': {'url': image.url}} for image in message.images)
    return HumanMessage(content=cast(list[str | dict[Any, Any]], parts))


def _render_text_with_image_urls(message: ChatMessage) -> str:
    rendered_text = message.text
    if not message.images:
        return rendered_text

    image_urls = '\n'.join(f'- {image.url}' for image in message.images)
    return f'{rendered_text}\n\nAttached image URLs:\n{image_urls}'


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
        rendered = '\n'.join(chunk for chunk in chunks if chunk)
        if rendered:
            return rendered

    return 'Sorry, I could not produce a response.'
