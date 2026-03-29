from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.chat import (
    ChatThreadNotFoundError,
    InvalidChatMessagesError,
    SendChatMessageUseCase,
)
from ai_video_gen_backend.domain.chat import (
    ChatImageInput,
    ChatInputMessage,
    ChatMessage,
    ChatRole,
    ChatThread,
)
from ai_video_gen_backend.infrastructure.providers import LangGraphChatWorkflow


class FakeChatRepository:
    def __init__(self) -> None:
        self._threads: dict[UUID, ChatThread] = {}
        self._messages_by_thread: dict[UUID, list[ChatMessage]] = {}

    def create_thread(self) -> ChatThread:
        now = datetime.now(UTC)
        thread = ChatThread(id=uuid4(), created_at=now, updated_at=now)
        self._threads[thread.id] = thread
        self._messages_by_thread[thread.id] = []
        return thread

    def get_thread_by_id(self, thread_id: UUID) -> ChatThread | None:
        return self._threads.get(thread_id)

    def list_messages(self, thread_id: UUID) -> list[ChatMessage]:
        return list(self._messages_by_thread.get(thread_id, []))

    def create_message(
        self,
        *,
        thread_id: UUID,
        role: ChatRole,
        text: str,
        image_urls: list[str],
    ) -> ChatMessage:
        now = datetime.now(UTC)
        message = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            role=role,
            text=text,
            images=[ChatImageInput(url=url) for url in image_urls],
            created_at=now,
        )
        self._messages_by_thread.setdefault(thread_id, []).append(message)
        return message


class FakeChatModel:
    def generate_reply(self, *, messages: list[ChatMessage]) -> str:
        latest = messages[-1]
        image_count = len(latest.images)
        return f'Received: {latest.text} ({image_count} images)'


def test_send_chat_message_use_case_runs_graph_and_persists_messages() -> None:
    repository = FakeChatRepository()
    workflow = LangGraphChatWorkflow(chat_repository=repository, chat_model=FakeChatModel())
    use_case = SendChatMessageUseCase(chat_repository=repository, chat_workflow=workflow)

    result = use_case.execute(
        thread_id=None,
        messages=[
            ChatInputMessage(
                role='user',
                text='Hello there',
                images=[ChatImageInput(url='https://example.com/a.png')],
            )
        ],
    )

    thread_messages = repository.list_messages(result.thread_id)
    assert len(thread_messages) == 2
    assert thread_messages[0].role == 'user'
    assert thread_messages[0].text == 'Hello there'
    assert thread_messages[1].role == 'assistant'
    assert thread_messages[1].text == 'Received: Hello there (1 images)'
    assert result.assistant_message.id == thread_messages[1].id


def test_send_chat_message_use_case_raises_when_thread_missing() -> None:
    repository = FakeChatRepository()
    workflow = LangGraphChatWorkflow(chat_repository=repository, chat_model=FakeChatModel())
    use_case = SendChatMessageUseCase(chat_repository=repository, chat_workflow=workflow)

    with pytest.raises(ChatThreadNotFoundError):
        use_case.execute(
            thread_id=uuid4(),
            messages=[ChatInputMessage(role='user', text='Hi', images=[])],
        )


def test_send_chat_message_use_case_raises_without_user_message() -> None:
    repository = FakeChatRepository()
    workflow = LangGraphChatWorkflow(chat_repository=repository, chat_model=FakeChatModel())
    use_case = SendChatMessageUseCase(chat_repository=repository, chat_workflow=workflow)

    with pytest.raises(InvalidChatMessagesError):
        use_case.execute(
            thread_id=None,
            messages=[ChatInputMessage(role='assistant', text='I can help', images=[])],
        )
