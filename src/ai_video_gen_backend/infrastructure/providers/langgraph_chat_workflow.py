from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage

from ai_video_gen_backend.domain.chat import (
    ChatAgentType,
    ChatInputMessage,
    ChatModelPort,
    ChatRepositoryPort,
    ChatStreamCancelledError,
    ChatWorkflowResult,
    ScreenplayChatContext,
    ScreenplayChatContextError,
)
from ai_video_gen_backend.domain.screenplay import Screenplay, ScreenplayRepositoryPort

from .screenplay_chat_tools import ScreenplayMutationTracker, build_screenplay_tools

SCREENPLAY_ASSISTANT_SYSTEM_PROMPT = """
You are a screenplay assistant for story and scene development.

Guidelines:
- Use screenplay conventions (sluglines, action lines, character names, parentheticals, dialogue).
- Read first: prefer read tools to inspect screenplay state before proposing edits.
- Only use write tools when the user explicitly asks to create, update, or delete scene content.
- Avoid broad rewrites unless the user clearly requests a broad rewrite.
- Ask clarifying questions when the request is underdefined.
- Suggest multiple story directions when useful.
- If a tool returns a validation or domain error, explain it and either
  retry with corrected inputs or ask for clarification.
""".strip()


@dataclass(frozen=True, slots=True)
class ChatWorkflowStreamOperation:
    type: str
    path: list[str | int]
    value: object


class _AgentUpdatesStreamingPort(Protocol):
    def astream(
        self,
        input: dict[str, object],
        *,
        stream_mode: str,
        config: dict[str, object] | None = None,
    ) -> AsyncIterator[object]: ...


def _create_tool_agent(
    *,
    model: object,
    tools: list[object],
    system_prompt: str,
    checkpointer: object | None = None,
) -> object:
    return create_agent(
        model=cast(Any, model),
        tools=cast(Any, tools),
        system_prompt=system_prompt,
        checkpointer=cast(Any, checkpointer),
    )


class LangGraphChatWorkflow:
    def __init__(
        self,
        *,
        chat_repository: ChatRepositoryPort,
        chat_model: ChatModelPort,
        screenplay_repository: ScreenplayRepositoryPort,
        screenplay_checkpointer: object | None = None,
    ) -> None:
        self._chat_repository = chat_repository
        self._chat_model = chat_model
        self._screenplay_repository = screenplay_repository
        self._screenplay_checkpointer = screenplay_checkpointer

    def run(
        self,
        *,
        thread_id: UUID,
        latest_user_message: ChatInputMessage,
        agent_type: ChatAgentType,
        screenplay_context: ScreenplayChatContext | None,
    ) -> ChatWorkflowResult:
        if agent_type == 'screenplay_assistant':
            msg = 'screenplay assistant is stream-only'
            raise ValueError(msg)

        self._chat_repository.create_message(
            thread_id=thread_id,
            role='user',
            text=latest_user_message.text,
            image_urls=[image.url for image in latest_user_message.images],
        )
        thread_messages = self._chat_repository.list_messages(thread_id)
        assistant_text = self._chat_model.generate_reply(messages=thread_messages)

        assistant_message = self._chat_repository.create_message(
            thread_id=thread_id,
            role='assistant',
            text=assistant_text,
            image_urls=[],
        )
        return ChatWorkflowResult(
            assistant_message=assistant_message,
            did_mutate=False,
            updated_screenplay=None,
        )

    async def stream(
        self,
        *,
        thread_id: UUID,
        start_message_index: int,
        latest_user_message: ChatInputMessage,
        agent_type: ChatAgentType,
        screenplay_context: ScreenplayChatContext | None,
        is_cancelled: Callable[[], bool],
    ) -> AsyncIterator[ChatWorkflowStreamOperation]:
        _raise_if_stream_cancelled(is_cancelled)

        if agent_type != 'screenplay_assistant':
            msg = 'stream() only supports screenplay assistant'
            raise ValueError(msg)

        screenplay_context = _require_screenplay_context(screenplay_context)
        if self._screenplay_checkpointer is None:
            msg = 'screenplay stream requires a configured LangGraph checkpointer'
            raise RuntimeError(msg)
        _require_screenplay(
            repository=self._screenplay_repository,
            screenplay_context=screenplay_context,
        )
        mutation_tracker = ScreenplayMutationTracker()
        tools = build_screenplay_tools(
            screenplay_repository=self._screenplay_repository,
            screenplay_context=screenplay_context,
            mutation_tracker=mutation_tracker,
            is_cancelled=is_cancelled,
        )
        agent = cast(
            _AgentUpdatesStreamingPort,
            _create_tool_agent(
                model=self._chat_model.as_langchain_chat_model(),
                tools=tools,
                system_prompt=SCREENPLAY_ASSISTANT_SYSTEM_PROMPT,
                checkpointer=self._screenplay_checkpointer,
            ),
        )

        assistant_text = ''
        message_index = start_message_index
        tool_name_by_call_id: dict[str, str] = {}
        # Durable SQL chat thread IDs are reused as LangGraph thread IDs.
        # This keeps assistant memory in checkpoints while avoiding SQL transcripts.
        checkpoint_config: dict[str, object] = {'configurable': {'thread_id': str(thread_id)}}

        async for update in agent.astream(
            {
                'messages': [
                    {
                        'role': latest_user_message.role,
                        'content': latest_user_message.text,
                    }
                ]
            },
            stream_mode='updates',
            config=checkpoint_config,
        ):
            _raise_if_stream_cancelled(is_cancelled)
            for message in _extract_messages_from_update(update):
                for activity in _tool_activities_from_update_message(
                    message=message,
                    tool_name_by_call_id=tool_name_by_call_id,
                ):
                    yield ChatWorkflowStreamOperation(
                        type='set',
                        path=['toolActivity'],
                        value=activity,
                    )

                maybe_assistant = _assistant_text_from_update_message(message)
                if maybe_assistant is not None:
                    assistant_text = maybe_assistant

        if not assistant_text:
            assistant_text = 'Could you clarify what you want me to do with the screenplay?'

        if mutation_tracker.did_mutate:
            updated_screenplay = _refetch_updated_screenplay(
                repository=self._screenplay_repository,
                screenplay_context=screenplay_context,
            )
            yield ChatWorkflowStreamOperation(
                type='set',
                path=['updatedScreenplay'],
                value=updated_screenplay,
            )

        # Tool status is streamed separately from assistant messages.
        # Clear it before publishing the final assistant text.
        yield ChatWorkflowStreamOperation(
            type='set',
            path=['toolActivity'],
            value=None,
        )
        yield ChatWorkflowStreamOperation(
            type='set',
            path=['messages', message_index],
            value={
                'role': 'assistant',
                'parts': [{'type': 'text', 'text': assistant_text}],
            },
        )
        _raise_if_stream_cancelled(is_cancelled)


def _raise_if_stream_cancelled(is_cancelled: Callable[[], bool] | None) -> None:
    if is_cancelled is not None and is_cancelled():
        raise ChatStreamCancelledError('Streaming chat request was cancelled')


def _require_screenplay_context(
    screenplay_context: ScreenplayChatContext | None,
) -> ScreenplayChatContext:
    if screenplay_context is None:
        raise ScreenplayChatContextError('Missing screenplay chat context')
    return screenplay_context


def _require_screenplay(
    *,
    repository: ScreenplayRepositoryPort,
    screenplay_context: ScreenplayChatContext,
) -> Screenplay:
    screenplay = repository.get_screenplay_by_project_id(screenplay_context.project_id)
    if screenplay is None or screenplay.id != screenplay_context.screenplay_id:
        raise ScreenplayChatContextError('Screenplay context points to missing screenplay')
    return screenplay


def _refetch_updated_screenplay(
    *,
    repository: ScreenplayRepositoryPort,
    screenplay_context: ScreenplayChatContext,
) -> Screenplay:
    updated_screenplay = repository.get_screenplay_by_project_id(screenplay_context.project_id)
    if updated_screenplay is None or updated_screenplay.id != screenplay_context.screenplay_id:
        msg = 'Screenplay mutation succeeded but refetch failed'
        raise RuntimeError(msg)
    return updated_screenplay


def _extract_messages_from_update(update: object) -> list[object]:
    messages: list[object] = []
    visited: set[int] = set()

    def _walk(value: object) -> None:
        value_id = id(value)
        if value_id in visited:
            return
        visited.add(value_id)

        if _is_message_object(value):
            messages.append(value)
            return

        if isinstance(value, dict):
            nested_messages = value.get('messages')
            if nested_messages is not None:
                _walk(nested_messages)
            for nested in value.values():
                if isinstance(nested, (dict, list, tuple)):
                    _walk(nested)
            return

        if isinstance(value, (list, tuple)):
            for nested in value:
                _walk(nested)

    _walk(update)
    return messages


def _is_message_object(value: object) -> bool:
    if isinstance(value, (AIMessage, ToolMessage)):
        return True

    if isinstance(value, dict) and 'content' in value:
        role = value.get('role')
        message_type = value.get('type')
        if role in {'assistant', 'ai', 'tool'}:
            return True
        return message_type in {'assistant', 'ai', 'tool'}

    return False


def _tool_activities_from_update_message(
    *,
    message: object,
    tool_name_by_call_id: dict[str, str],
) -> list[str]:
    activities: list[str] = []

    for tool_call in _extract_tool_calls(message):
        name = tool_call.get('name')
        if not isinstance(name, str) or not name:
            continue
        tool_call_id = tool_call.get('id')
        if isinstance(tool_call_id, str) and tool_call_id:
            if tool_call_id in tool_name_by_call_id:
                continue
            tool_name_by_call_id[tool_call_id] = name
        activities.append(_tool_activity_start_text(name))

    tool_result = _extract_tool_result_message(
        message=message,
        tool_name_by_call_id=tool_name_by_call_id,
    )
    if tool_result is not None:
        activities.append(
            _tool_activity_from_tool_result(
                tool_name=tool_result.tool_name,
                output=tool_result.output,
                status=tool_result.status,
            )
        )

    return activities


@dataclass(frozen=True, slots=True)
class _ToolResultMessage:
    tool_name: str
    output: object
    status: str | None


def _extract_tool_calls(message: object) -> list[dict[str, object]]:
    if isinstance(message, AIMessage):
        tool_calls: list[dict[str, object]] = []
        for call in message.tool_calls:
            if isinstance(call, dict):
                tool_calls.append(cast(dict[str, object], call))
        return tool_calls
    if isinstance(message, dict):
        raw_tool_calls = message.get('tool_calls')
        if isinstance(raw_tool_calls, list):
            return [call for call in raw_tool_calls if isinstance(call, dict)]
    return []


def _extract_tool_result_message(
    *,
    message: object,
    tool_name_by_call_id: dict[str, str],
) -> _ToolResultMessage | None:
    if isinstance(message, ToolMessage):
        tool_name = message.name
        if tool_name is None and message.tool_call_id in tool_name_by_call_id:
            tool_name = tool_name_by_call_id[message.tool_call_id]
        if not isinstance(tool_name, str) or not tool_name:
            return None
        return _ToolResultMessage(
            tool_name=tool_name,
            output=message.content,
            status=message.status,
        )

    if isinstance(message, dict):
        role = message.get('role')
        message_type = message.get('type')
        if role != 'tool' and message_type != 'tool':
            return None

        tool_name = message.get('name')
        if not isinstance(tool_name, str) or not tool_name:
            tool_call_id = message.get('tool_call_id')
            if isinstance(tool_call_id, str):
                tool_name = tool_name_by_call_id.get(tool_call_id)
        if not isinstance(tool_name, str) or not tool_name:
            return None

        raw_status = message.get('status')
        status = raw_status if isinstance(raw_status, str) else None
        return _ToolResultMessage(
            tool_name=tool_name,
            output=message.get('content'),
            status=status,
        )

    return None


def _tool_activity_from_tool_result(*, tool_name: str, output: object, status: str | None) -> str:
    if isinstance(status, str) and status.lower() in {'error', 'failed', 'failure'}:
        parsed = _tool_result_payload_from_output(output)
        if isinstance(parsed, dict):
            message = parsed.get('message')
            if isinstance(message, str) and message:
                return message
        return 'Tool execution failed'

    parsed = _tool_result_payload_from_output(output)
    if parsed is None:
        return _tool_activity_success_text(tool_name)

    parsed_status = parsed.get('status')
    if isinstance(parsed_status, str):
        normalized_status = parsed_status.strip().lower()
        if normalized_status in {'ok', 'success'}:
            return _tool_activity_success_text(tool_name)
        if normalized_status in {'error', 'failed', 'failure'}:
            message = parsed.get('message')
            if isinstance(message, str) and message:
                return message
            return _tool_activity_failure_text(tool_name)

    message = parsed.get('message')
    code = parsed.get('code')
    if isinstance(code, str) and 'error' in code.lower() and isinstance(message, str) and message:
        return message
    return _tool_activity_success_text(tool_name)


def _assistant_text_from_update_message(message: object) -> str | None:
    if isinstance(message, AIMessage):
        if message.tool_calls:
            return None
        return _extract_text_from_content(message.content)

    if isinstance(message, dict):
        role = message.get('role')
        if role not in {'assistant', 'ai'} and message.get('type') not in {'assistant', 'ai'}:
            return None
        tool_calls = message.get('tool_calls')
        if isinstance(tool_calls, list) and tool_calls:
            return None
        return _extract_text_from_content(message.get('content'))

    return None


def _tool_result_payload_from_output(output: object) -> dict[str, object] | None:
    if isinstance(output, dict):
        return output
    if isinstance(output, str):
        return _json_dict_from_text(output)
    if isinstance(output, list):
        for item in output:
            parsed = _tool_result_payload_from_output(item)
            if parsed is not None:
                return parsed
        return None

    content = getattr(output, 'content', None)
    if content is not None:
        return _tool_result_payload_from_output(content)
    return None


def _json_dict_from_text(text: str) -> dict[str, object] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _tool_activity_start_text(tool_name: str) -> str:
    return {
        'get_screenplay_overview': 'Checking screenplay structure...',
        'get_scene': 'Reading scene content...',
        'create_scene': 'Creating a new scene...',
        'update_scene': 'Updating scene content...',
        'delete_scene': 'Deleting scene...',
    }.get(tool_name, f'Running tool: {tool_name}')


def _tool_activity_success_text(tool_name: str) -> str:
    return {
        'get_screenplay_overview': 'Loaded screenplay structure.',
        'get_scene': 'Scene content loaded.',
        'create_scene': 'Created a new scene.',
        'update_scene': 'Scene update applied.',
        'delete_scene': 'Scene deleted.',
    }.get(tool_name, f'Tool completed: {tool_name}')


def _tool_activity_failure_text(tool_name: str) -> str:
    return {
        'get_screenplay_overview': 'Could not load screenplay structure.',
        'get_scene': 'Could not read scene content.',
        'create_scene': 'Could not create the scene.',
        'update_scene': 'Could not update the scene.',
        'delete_scene': 'Could not delete the scene.',
    }.get(tool_name, 'Tool execution failed')


def _extract_text_from_content(content: object) -> str | None:
    if isinstance(content, str) and content:
        return content

    if isinstance(content, list):
        text_chunks: list[str] = []
        for part in content:
            if isinstance(part, dict):
                value = part.get('text')
                if isinstance(value, str) and value:
                    text_chunks.append(value)
        if text_chunks:
            return '\n'.join(text_chunks)

    return None
