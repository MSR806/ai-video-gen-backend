from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, HttpUrl

from ai_video_gen_backend.domain.chat import SendChatResult
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class ChatImageRequest(StrictSchema):
    url: HttpUrl


class ChatMessageRequest(StrictSchema):
    role: Literal['user', 'assistant']
    text: str = Field(min_length=1)
    images: list[ChatImageRequest] = Field(default_factory=list)


class ChatRequest(StrictSchema):
    thread_id: UUID | None = Field(default=None, alias='threadId')
    messages: list[ChatMessageRequest] = Field(min_length=1)


class ChatImageResponse(StrictSchema):
    url: HttpUrl


class AssistantMessageResponse(StrictSchema):
    role: Literal['assistant']
    text: str
    images: list[ChatImageResponse]
    created_at: datetime = Field(alias='createdAt')


class ChatResponse(StrictSchema):
    thread_id: UUID = Field(alias='threadId')
    message: AssistantMessageResponse

    @classmethod
    def from_domain(cls, result: SendChatResult) -> ChatResponse:
        return cls(
            thread_id=result.thread_id,
            message=AssistantMessageResponse(
                role='assistant',
                text=result.assistant_message.text,
                images=[
                    ChatImageResponse(url=image.url) for image in result.assistant_message.images
                ],
                created_at=result.assistant_message.created_at,
            ),
        )
