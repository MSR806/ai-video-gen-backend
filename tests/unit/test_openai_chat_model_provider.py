from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from langchain_core.messages import HumanMessage

from ai_video_gen_backend.domain.chat import ChatImageInput, ChatMessage
from ai_video_gen_backend.infrastructure.providers.openai_chat_model_provider import (
    _extract_text,
    _to_langchain_message,
)


def test_to_langchain_message_user_text_only_uses_string_content() -> None:
    message = _build_chat_message(text='hello', image_urls=[])

    mapped = _to_langchain_message(message)

    assert isinstance(mapped, HumanMessage)
    assert mapped.content == 'hello'


def test_to_langchain_message_user_text_and_images_uses_multimodal_parts() -> None:
    message = _build_chat_message(
        text='Please describe these images.',
        image_urls=['https://example.test/1.png', 'https://example.test/2.png'],
    )

    mapped = _to_langchain_message(message)

    assert isinstance(mapped, HumanMessage)
    assert mapped.content == [
        {'type': 'text', 'text': 'Please describe these images.'},
        {'type': 'image_url', 'image_url': {'url': 'https://example.test/1.png'}},
        {'type': 'image_url', 'image_url': {'url': 'https://example.test/2.png'}},
    ]


def test_extract_text_reads_text_from_content_chunks() -> None:
    extracted = _extract_text(
        [
            {'type': 'text', 'text': 'first'},
            {'type': 'image_url', 'image_url': {'url': 'https://example.test/1.png'}},
            {'type': 'text', 'text': 'second'},
        ]
    )

    assert extracted == 'first\nsecond'


def _build_chat_message(*, text: str, image_urls: list[str]) -> ChatMessage:
    now = datetime.now(tz=UTC)
    return ChatMessage(
        id=uuid4(),
        thread_id=uuid4(),
        role='user',
        text=text,
        images=[ChatImageInput(url=url) for url in image_urls],
        created_at=now,
    )
