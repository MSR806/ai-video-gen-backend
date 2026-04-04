from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.chat import (
    ChatAgentType,
    ChatInputMessage,
    ChatRepositoryPort,
    ChatWorkflowPort,
    ScreenplayChatContext,
    SendChatResult,
)


class ChatThreadNotFoundError(Exception):
    """Raised when a chat thread cannot be found."""


class InvalidChatMessagesError(Exception):
    """Raised when request messages do not contain any user message."""


class InvalidScreenplayChatContextError(Exception):
    """Raised when screenplay assistant context is missing required fields."""


class ScreenplayAssistantRequiresStreamingError(Exception):
    """Raised when screenplay assistant is called on sync chat path."""


class SendChatMessageUseCase:
    def __init__(
        self,
        chat_repository: ChatRepositoryPort,
        chat_workflow: ChatWorkflowPort,
    ) -> None:
        self._chat_repository = chat_repository
        self._chat_workflow = chat_workflow

    def execute(
        self,
        *,
        thread_id: UUID | None,
        messages: list[ChatInputMessage],
        agent_type: ChatAgentType,
        screenplay_context: ScreenplayChatContext | None,
    ) -> SendChatResult:
        latest_user_message = _latest_user_message(messages)

        if agent_type == 'screenplay_assistant':
            raise ScreenplayAssistantRequiresStreamingError

        thread = (
            self._chat_repository.create_thread()
            if thread_id is None
            else self._chat_repository.get_thread_by_id(thread_id)
        )
        if thread is None:
            raise ChatThreadNotFoundError

        workflow_result = self._chat_workflow.run(
            thread_id=thread.id,
            latest_user_message=latest_user_message,
            agent_type=agent_type,
            screenplay_context=screenplay_context,
        )

        return SendChatResult(
            thread_id=thread.id,
            assistant_message=workflow_result.assistant_message,
            did_mutate=workflow_result.did_mutate,
            updated_screenplay=workflow_result.updated_screenplay,
        )


def _latest_user_message(messages: list[ChatInputMessage]) -> ChatInputMessage:
    for message in reversed(messages):
        if message.role == 'user':
            return message

    raise InvalidChatMessagesError
