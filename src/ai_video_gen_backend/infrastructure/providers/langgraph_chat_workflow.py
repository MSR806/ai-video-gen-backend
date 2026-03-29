from __future__ import annotations

from typing import Protocol, TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from ai_video_gen_backend.domain.chat import (
    ChatInputMessage,
    ChatMessage,
    ChatModelPort,
    ChatRepositoryPort,
)


class _ChatWorkflowState(TypedDict, total=False):
    thread_id: UUID
    latest_user_message: ChatInputMessage
    assistant_text: str
    assistant_message: ChatMessage


class _CompiledGraphPort(Protocol):
    def invoke(self, input: _ChatWorkflowState) -> dict[str, object]: ...


class LangGraphChatWorkflow:
    def __init__(self, *, chat_repository: ChatRepositoryPort, chat_model: ChatModelPort) -> None:
        self._chat_repository = chat_repository
        self._chat_model = chat_model

        graph = StateGraph(_ChatWorkflowState)
        graph.add_node('persist_user_message', self._persist_user_message)
        graph.add_node('call_model', self._call_model)
        graph.add_node('persist_assistant_message', self._persist_assistant_message)
        graph.add_edge(START, 'persist_user_message')
        graph.add_edge('persist_user_message', 'call_model')
        graph.add_edge('call_model', 'persist_assistant_message')
        graph.add_edge('persist_assistant_message', END)
        self._compiled_graph = cast(_CompiledGraphPort, graph.compile())

    def run(self, *, thread_id: UUID, latest_user_message: ChatInputMessage) -> ChatMessage:
        state: _ChatWorkflowState = {
            'thread_id': thread_id,
            'latest_user_message': latest_user_message,
        }
        result = self._compiled_graph.invoke(state)
        assistant_message = result.get('assistant_message')
        if not isinstance(assistant_message, ChatMessage):
            msg = 'Assistant message missing from chat workflow result'
            raise RuntimeError(msg)
        return assistant_message

    def _persist_user_message(self, state: _ChatWorkflowState) -> _ChatWorkflowState:
        thread_id = state['thread_id']
        user_message = state['latest_user_message']
        self._chat_repository.create_message(
            thread_id=thread_id,
            role='user',
            text=user_message.text,
            image_urls=[image.url for image in user_message.images],
        )
        return {}

    def _call_model(self, state: _ChatWorkflowState) -> _ChatWorkflowState:
        thread_id = state['thread_id']
        thread_messages = self._chat_repository.list_messages(thread_id)
        assistant_text = self._chat_model.generate_reply(messages=thread_messages)
        return {'assistant_text': assistant_text}

    def _persist_assistant_message(self, state: _ChatWorkflowState) -> _ChatWorkflowState:
        thread_id = state['thread_id']
        assistant_text = state['assistant_text']
        assistant_message = self._chat_repository.create_message(
            thread_id=thread_id,
            role='assistant',
            text=assistant_text,
            image_urls=[],
        )
        return {'assistant_message': assistant_message}
