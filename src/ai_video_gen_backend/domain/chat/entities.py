from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

ChatRole = Literal['user', 'assistant']


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
