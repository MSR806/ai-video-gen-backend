from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AIMessage, ToolMessage

from ai_video_gen_backend.infrastructure.providers.langgraph_chat_workflow import (
    _assistant_text_from_update_message,
    _extract_messages_from_update,
    _tool_activities_from_update_message,
)


def test_extract_messages_from_updates_collects_nested_messages() -> None:
    update: dict[str, object] = {
        'model': {
            'messages': [
                AIMessage(
                    content='',
                    tool_calls=[{'id': 'call-1', 'name': 'get_scene', 'args': {}}],
                )
            ]
        },
        'tools': {'messages': [ToolMessage(name='get_scene', tool_call_id='call-1', content='{}')]},
    }

    messages = _extract_messages_from_update(update)
    assert len(messages) == 2
    assert isinstance(messages[0], AIMessage)
    assert isinstance(messages[1], ToolMessage)


def test_tool_activities_from_update_message_tracks_start_and_success() -> None:
    tool_name_by_call_id: dict[str, str] = {}
    start_message = AIMessage(
        content='',
        tool_calls=[{'id': 'call-1', 'name': 'get_scene', 'args': {}}],
    )
    completion_message = ToolMessage(
        name='get_scene',
        tool_call_id='call-1',
        content='{"status":"ok"}',
        status='success',
    )

    start_activities = _tool_activities_from_update_message(
        message=start_message,
        tool_name_by_call_id=tool_name_by_call_id,
    )
    completion_activities = _tool_activities_from_update_message(
        message=completion_message,
        tool_name_by_call_id=tool_name_by_call_id,
    )

    assert start_activities == ['Reading scene content...']
    assert completion_activities == ['Scene content loaded.']


def test_tool_activities_from_update_message_parses_tool_message_content_error() -> None:
    tool_name_by_call_id = {'call-1': 'update_scene'}

    @dataclass
    class _ToolLike:
        content: object

    completion_message: dict[str, object] = {
        'role': 'tool',
        'tool_call_id': 'call-1',
        'content': _ToolLike(content='{"status":"error","message":"Invalid XML"}'),
        'status': 'error',
    }
    activities = _tool_activities_from_update_message(
        message=completion_message,
        tool_name_by_call_id=tool_name_by_call_id,
    )

    assert activities == ['Invalid XML']


def test_assistant_text_from_update_message_ignores_tool_call_steps() -> None:
    tool_request_message = AIMessage(
        content='thinking',
        tool_calls=[{'id': 'call-1', 'name': 'get_scene', 'args': {}}],
    )
    final_message = AIMessage(content='Final assistant answer.')

    assert _assistant_text_from_update_message(tool_request_message) is None
    assert _assistant_text_from_update_message(final_message) == 'Final assistant answer.'
