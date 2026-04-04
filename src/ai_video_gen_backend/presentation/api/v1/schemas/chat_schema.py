from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, HttpUrl

from ai_video_gen_backend.domain.chat import SendChatResult
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema
from ai_video_gen_backend.presentation.api.v1.schemas.screenplay_schema import ScreenplayResponse


class ChatImageRequest(StrictSchema):
    url: HttpUrl


class ChatMessageRequest(StrictSchema):
    role: Literal['user', 'assistant']
    text: str = Field(min_length=1)
    images: list[ChatImageRequest] = Field(default_factory=list)


class ChatRequest(StrictSchema):
    thread_id: UUID | None = Field(default=None, alias='threadId')
    messages: list[ChatMessageRequest] = Field(min_length=1)
    agent_type: Literal['default', 'screenplay_assistant'] = Field(
        default='default', alias='agentType'
    )
    project_id: UUID | None = Field(default=None, alias='projectId')
    screenplay_id: UUID | None = Field(default=None, alias='screenplayId')
    active_scene_id: UUID | None = Field(default=None, alias='activeSceneId')


class AssistantTransportMessagePart(StrictSchema):
    type: str
    text: str | None = None
    data: dict[str, object] | None = None
    name: str | None = None


class AssistantTransportMessage(StrictSchema):
    role: str
    parts: list[AssistantTransportMessagePart] = Field(default_factory=list)


class AssistantTransportCommand(StrictSchema):
    type: str
    message: AssistantTransportMessage | None = None
    parent_id: str | None = Field(default=None, alias='parentId')
    source_id: str | None = Field(default=None, alias='sourceId')


class ChatStreamRequest(StrictSchema):
    thread_id: UUID | None = Field(default=None, alias='threadId')
    agent_type: Literal['screenplay_assistant'] = Field(
        default='screenplay_assistant', alias='agentType'
    )
    project_id: UUID | None = Field(default=None, alias='projectId')
    screenplay_id: UUID | None = Field(default=None, alias='screenplayId')
    active_scene_id: UUID | None = Field(default=None, alias='activeSceneId')
    state: dict[str, object] | None = None
    commands: list[AssistantTransportCommand] = Field(min_length=1)
    system: str | None = None
    tools: dict[str, object] | None = None
    parent_id: str | None = Field(default=None, alias='parentId')
    call_settings: dict[str, object] | None = Field(default=None, alias='callSettings')
    config: dict[str, object] | None = None


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
    did_mutate: bool = Field(default=False, alias='didMutate')
    updated_screenplay: ScreenplayResponse | None = Field(default=None, alias='updatedScreenplay')

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
            did_mutate=result.did_mutate,
            updated_screenplay=(
                ScreenplayResponse.from_domain(result.updated_screenplay)
                if result.updated_screenplay is not None
                else None
            ),
        )
