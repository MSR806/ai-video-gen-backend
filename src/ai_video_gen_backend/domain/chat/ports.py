from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import (
    ChatAgentType,
    ChatInputMessage,
    ChatMessage,
    ChatRole,
    ChatThread,
    ChatWorkflowResult,
    ScreenplayChatContext,
)


class ChatRepositoryPort(Protocol):
    def create_thread(self) -> ChatThread: ...

    def get_thread_by_id(self, thread_id: UUID) -> ChatThread | None: ...

    def list_messages(self, thread_id: UUID) -> list[ChatMessage]: ...

    def create_message(
        self,
        *,
        thread_id: UUID,
        role: ChatRole,
        text: str,
        image_urls: list[str],
    ) -> ChatMessage: ...


class ChatModelPort(Protocol):
    def generate_reply(self, *, messages: list[ChatMessage]) -> str: ...

    def as_langchain_chat_model(self) -> object: ...


class ChatWorkflowPort(Protocol):
    def run(
        self,
        *,
        thread_id: UUID,
        latest_user_message: ChatInputMessage,
        agent_type: ChatAgentType,
        screenplay_context: ScreenplayChatContext | None,
    ) -> ChatWorkflowResult: ...
