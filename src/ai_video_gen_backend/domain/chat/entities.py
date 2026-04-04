from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from ai_video_gen_backend.domain.screenplay import Screenplay

ChatRole = Literal['user', 'assistant']
ChatAgentType = Literal['default', 'screenplay_assistant']


class ScreenplayChatContextError(Exception):
    """Raised when screenplay chat context references missing entities."""


class ChatStreamCancelledError(Exception):
    """Raised when streaming chat execution is cancelled by client disconnect."""


@dataclass(frozen=True, slots=True)
class ChatImageInput:
    url: str


@dataclass(frozen=True, slots=True)
class ChatInputMessage:
    role: ChatRole
    text: str
    images: list[ChatImageInput]


@dataclass(frozen=True, slots=True)
class ChatThread:
    id: UUID
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChatMessage:
    id: UUID
    thread_id: UUID
    role: ChatRole
    text: str
    images: list[ChatImageInput]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SendChatResult:
    thread_id: UUID
    assistant_message: ChatMessage
    did_mutate: bool = False
    updated_screenplay: Screenplay | None = None


@dataclass(frozen=True, slots=True)
class ScreenplayChatContext:
    project_id: UUID
    screenplay_id: UUID
    active_scene_id: UUID | None


@dataclass(frozen=True, slots=True)
class ChatWorkflowResult:
    assistant_message: ChatMessage
    did_mutate: bool = False
    updated_screenplay: Screenplay | None = None
