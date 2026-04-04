from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from typing import Protocol, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.chat import ChatMessage
from ai_video_gen_backend.infrastructure.providers import langgraph_chat_workflow
from ai_video_gen_backend.infrastructure.repositories import (
    ChatSqlRepository,
    ScreenplaySqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import get_chat_model_provider
from tests.support import seed_baseline_data


class FakeChatModelProvider:
    def generate_reply(self, *, messages: list[ChatMessage]) -> str:
        latest_user_text = ''
        for message in reversed(messages):
            if message.role == 'user':
                latest_user_text = message.text
                break
        return f'Assistant reply to: {latest_user_text}'

    def as_langchain_chat_model(self) -> object:
        return object()


class _NamedTool(Protocol):
    name: str

    def invoke(self, input: dict[str, object]) -> dict[str, object]: ...


class _TransportStreamResponse(Protocol):
    def iter_lines(self) -> Iterable[str | bytes]: ...


def _collect_assistant_transport_chunks(
    response: _TransportStreamResponse,
) -> tuple[list[dict[str, object]], list[str]]:
    operations: list[dict[str, object]] = []
    errors: list[str] = []

    for line in response.iter_lines():
        if isinstance(line, bytes):
            line = line.decode('utf-8')
        if not isinstance(line, str):
            continue

        if not line:
            continue

        if line.startswith('aui-state:'):
            payload = json.loads(line.removeprefix('aui-state:'))
            if isinstance(payload, list):
                operations.extend(op for op in payload if isinstance(op, dict))
            continue

        if line.startswith('3:'):
            payload = json.loads(line.removeprefix('3:'))
            if isinstance(payload, str):
                errors.append(payload)

    return operations, errors


def test_post_chat_creates_new_thread(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
) -> None:
    del db_session
    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    response = client.post(
        '/api/v1/chat',
        json={
            'messages': [
                {
                    'role': 'user',
                    'text': 'What is clean architecture?',
                    'images': [{'url': 'https://example.com/diagram.png'}],
                }
            ]
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['threadId']
    assert payload['message']['role'] == 'assistant'
    assert payload['message']['text'] == 'Assistant reply to: What is clean architecture?'
    assert payload['didMutate'] is False
    assert payload['updatedScreenplay'] is None


def test_post_chat_response_matches_frontend_contract(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
) -> None:
    del db_session
    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    response = client.post(
        '/api/v1/chat',
        json={
            'messages': [
                {
                    'role': 'user',
                    'text': 'Contract test',
                }
            ]
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {'threadId', 'message', 'didMutate', 'updatedScreenplay'}
    assert isinstance(payload['threadId'], str)
    assert set(payload['message'].keys()) == {'role', 'text', 'images', 'createdAt'}
    assert payload['message']['role'] == 'assistant'
    assert isinstance(payload['message']['text'], str)
    assert payload['didMutate'] is False
    assert payload['updatedScreenplay'] is None


def test_post_chat_continues_existing_thread(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
) -> None:
    repository = ChatSqlRepository(db_session)
    thread = repository.create_thread()
    repository.create_message(
        thread_id=thread.id,
        role='user',
        text='First question',
        image_urls=[],
    )
    repository.create_message(
        thread_id=thread.id,
        role='assistant',
        text='First answer',
        image_urls=[],
    )

    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    response = client.post(
        '/api/v1/chat',
        json={
            'threadId': str(thread.id),
            'messages': [{'role': 'user', 'text': 'Second question'}],
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['threadId'] == str(thread.id)
    assert payload['message']['text'] == 'Assistant reply to: Second question'


def test_post_chat_returns_validation_error_for_bad_payload(client: TestClient) -> None:
    response = client.post(
        '/api/v1/chat',
        json={
            'messages': [{'role': 'system', 'text': 123}],
            'unknown': True,
        },
    )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'


def test_post_chat_returns_404_for_unknown_thread_id(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
) -> None:
    del db_session
    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    response = client.post(
        '/api/v1/chat',
        json={
            'threadId': '00000000-0000-0000-0000-000000000001',
            'messages': [{'role': 'user', 'text': 'Ping'}],
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    payload = response.json()
    assert payload['error']['code'] == 'thread_not_found'


def test_screenplay_assistant_is_rejected_on_sync_chat_path(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
) -> None:
    del db_session
    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    response = client.post(
        '/api/v1/chat',
        json={
            'agentType': 'screenplay_assistant',
            'messages': [{'role': 'user', 'text': 'Rewrite this scene'}],
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'screenplay_requires_stream'


def test_post_chat_stream_rejects_default_agent_type(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
) -> None:
    del db_session
    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    response = client.post(
        '/api/v1/chat/stream',
        json={
            'agentType': 'default',
            'commands': [
                {
                    'type': 'add-message',
                    'message': {
                        'role': 'user',
                        'parts': [{'type': 'text', 'text': 'Stream this reply'}],
                    },
                }
            ],
        },
    )
    assert response.status_code == 422

    app.dependency_overrides.clear()

    assert response.json()['error']['code'] == 'validation_error'


def test_post_chat_stream_emits_single_final_text_from_ai_message_chunks(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = seed_baseline_data(db_session)
    project_id = ids['project_id']
    create = client.post(
        f'/api/v1/projects/{project_id}/screenplays',
        json={'title': 'Pilot'},
    )
    screenplay_id = create.json()['id']

    class ChunkStreamingAgent:
        async def astream(
            self,
            input: dict[str, object],
            *,
            stream_mode: str,
            config: dict[str, object] | None = None,
        ) -> AsyncIterator[object]:
            del input
            assert stream_mode == 'updates'
            assert isinstance(config, dict)
            configurable = config.get('configurable')
            assert isinstance(configurable, dict)
            assert isinstance(configurable.get('thread_id'), str)
            yield {
                'model': {
                    'messages': [
                        AIMessage(
                            content='',
                            tool_calls=[{'id': 'call-1', 'name': 'get_scene', 'args': {}}],
                        )
                    ]
                }
            }
            yield {
                'tools': {
                    'messages': [
                        ToolMessage(
                            name='get_scene',
                            tool_call_id='call-1',
                            content='{"status":"ok"}',
                            status='success',
                        )
                    ]
                }
            }
            yield {
                'model': {
                    'messages': [
                        AIMessage(content='Chunk one chunk two'),
                    ]
                }
            }

    monkeypatch.setattr(
        langgraph_chat_workflow,
        '_create_tool_agent',
        lambda **kwargs: cast(object, ChunkStreamingAgent()),
    )
    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    with client.stream(
        'POST',
        '/api/v1/chat/stream',
        json={
            'projectId': str(project_id),
            'screenplayId': screenplay_id,
            'state': {'messages': []},
            'commands': [
                {
                    'type': 'add-message',
                    'message': {
                        'role': 'user',
                        'parts': [{'type': 'text', 'text': 'Stream chunked assistant output'}],
                    },
                }
            ],
        },
    ) as response:
        operations, errors = _collect_assistant_transport_chunks(response)

    app.dependency_overrides.clear()

    text_parts = []
    for operation in operations:
        path = operation.get('path')
        value = operation.get('value')
        if not isinstance(path, list) or path[:1] != ['messages']:
            continue
        if not isinstance(value, dict):
            continue
        if value.get('role') != 'assistant':
            continue
        parts = value.get('parts')
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and part.get('type') == 'text':
                text = part.get('text')
                if isinstance(text, str):
                    text_parts.append(text)

    assert text_parts == ['Chunk one chunk two']
    assert errors == []
    thread_id = next(
        (op.get('value') for op in operations if op.get('path') == ['threadId']),
        None,
    )
    assert isinstance(thread_id, str)

    repository = ChatSqlRepository(db_session)
    assert repository.list_messages(UUID(thread_id)) == []


def test_post_chat_stream_screenplay_mutation_emits_tool_activity_state_and_updated_screenplay(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = seed_baseline_data(db_session)
    project_id = ids['project_id']
    create = client.post(
        f'/api/v1/projects/{project_id}/screenplays',
        json={'title': 'Pilot'},
    )
    screenplay_id = create.json()['id']

    class MutationAgent:
        def __init__(self, *, tools: list[object]) -> None:
            self._tools = {cast(_NamedTool, tool).name: cast(_NamedTool, tool) for tool in tools}

        async def astream(
            self,
            input: dict[str, object],
            *,
            stream_mode: str,
            config: dict[str, object] | None = None,
        ) -> AsyncIterator[object]:
            del input
            assert stream_mode == 'updates'
            assert isinstance(config, dict)
            yield {
                'model': {
                    'messages': [
                        AIMessage(
                            content='',
                            tool_calls=[
                                {
                                    'id': 'call-1',
                                    'name': 'create_scene',
                                    'args': {},
                                }
                            ],
                        )
                    ]
                }
            }
            create_result = self._tools['create_scene'].invoke(
                {
                    'content': '<scene><slugline>INT. LAB - NIGHT</slugline>'
                    '<action>The reactor hums.</action></scene>'
                }
            )
            yield {
                'tools': {
                    'messages': [
                        ToolMessage(
                            name='create_scene',
                            tool_call_id='call-1',
                            content=json.dumps(create_result),
                            status='success',
                        )
                    ]
                }
            }
            yield {
                'model': {
                    'messages': [
                        AIMessage(content='Done mutating.'),
                    ]
                },
            }

    def _agent_factory(**kwargs: object) -> object:
        tools = kwargs['tools']
        assert isinstance(tools, list)
        return MutationAgent(tools=cast(list[object], tools))

    monkeypatch.setattr(langgraph_chat_workflow, '_create_tool_agent', _agent_factory)
    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    with client.stream(
        'POST',
        '/api/v1/chat/stream',
        json={
            'projectId': str(project_id),
            'screenplayId': screenplay_id,
            'state': {'messages': []},
            'commands': [
                {
                    'type': 'add-message',
                    'message': {
                        'role': 'user',
                        'parts': [{'type': 'text', 'text': 'Add a scene and stream updates.'}],
                    },
                }
            ],
        },
    ) as response:
        operations, errors = _collect_assistant_transport_chunks(response)

    app.dependency_overrides.clear()

    tool_activity_values = [
        op.get('value') for op in operations if op.get('path') == ['toolActivity']
    ]
    assert 'Creating a new scene...' in tool_activity_values
    assert 'Created a new scene.' in tool_activity_values
    assert tool_activity_values[-1] is None

    final_assistant_operation = None
    for operation in reversed(operations):
        if operation.get('path') != ['messages', 1]:
            continue
        value = operation.get('value')
        if not isinstance(value, dict):
            continue
        if value.get('role') != 'assistant':
            continue
        final_assistant_operation = operation
        break
    assert isinstance(final_assistant_operation, dict)
    assert final_assistant_operation.get('value') == {
        'role': 'assistant',
        'parts': [{'type': 'text', 'text': 'Done mutating.'}],
    }
    updated = next(
        (op.get('value') for op in operations if op.get('path') == ['updatedScreenplay']),
        None,
    )
    assert isinstance(updated, dict)
    scenes = updated.get('scenes') if isinstance(updated, dict) else None
    assert isinstance(scenes, list)
    assert len(scenes) == 1
    assert errors == []


def test_post_chat_stream_emits_error_event_for_invalid_screenplay_context(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
) -> None:
    del db_session
    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    with client.stream(
        'POST',
        '/api/v1/chat/stream',
        json={
            'commands': [
                {
                    'type': 'add-message',
                    'message': {
                        'role': 'user',
                        'parts': [{'type': 'text', 'text': 'Rewrite this scene'}],
                    },
                }
            ],
        },
    ) as response:
        operations, errors = _collect_assistant_transport_chunks(response)

    app.dependency_overrides.clear()

    assert operations == [
        {
            'type': 'set',
            'path': ['toolActivity'],
            'value': None,
        }
    ]
    assert errors == ['projectId and screenplayId are required for screenplay assistant']


def test_post_chat_stream_tool_internal_exception_is_sanitized(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = seed_baseline_data(db_session)
    project_id = ids['project_id']
    create = client.post(
        f'/api/v1/projects/{project_id}/screenplays',
        json={'title': 'Pilot'},
    )
    screenplay_id = create.json()['id']

    class MutationAgent:
        def __init__(self, *, tools: list[object]) -> None:
            self._tools = {cast(_NamedTool, tool).name: cast(_NamedTool, tool) for tool in tools}

        async def astream(
            self,
            input: dict[str, object],
            *,
            stream_mode: str,
            config: dict[str, object] | None = None,
        ) -> AsyncIterator[object]:
            del input
            assert stream_mode == 'updates'
            assert isinstance(config, dict)
            yield {
                'model': {
                    'messages': [
                        AIMessage(
                            content='',
                            tool_calls=[
                                {
                                    'id': 'call-1',
                                    'name': 'create_scene',
                                    'args': {},
                                }
                            ],
                        )
                    ]
                }
            }
            try:
                self._tools['create_scene'].invoke(
                    {'content': '<scene><slugline>INT. LAB - NIGHT</slugline></scene>'}
                )
            except RuntimeError:
                yield {
                    'tools': {
                        'messages': [
                            ToolMessage(
                                name='create_scene',
                                tool_call_id='call-1',
                                content='{}',
                                status='error',
                            )
                        ]
                    }
                }
                raise

    def _agent_factory(**kwargs: object) -> object:
        tools = kwargs['tools']
        assert isinstance(tools, list)
        return MutationAgent(tools=cast(list[object], tools))

    def _raise_internal(
        self: ScreenplaySqlRepository,
        screenplay_id: UUID,
        payload: object,
    ) -> object:
        del self, screenplay_id, payload
        raise RuntimeError('db stacktrace: secret internals')

    monkeypatch.setattr(langgraph_chat_workflow, '_create_tool_agent', _agent_factory)
    monkeypatch.setattr(ScreenplaySqlRepository, 'create_screenplay_scene', _raise_internal)
    app.dependency_overrides[get_chat_model_provider] = lambda: FakeChatModelProvider()

    with client.stream(
        'POST',
        '/api/v1/chat/stream',
        json={
            'projectId': str(project_id),
            'screenplayId': screenplay_id,
            'state': {'messages': []},
            'commands': [
                {
                    'type': 'add-message',
                    'message': {
                        'role': 'user',
                        'parts': [{'type': 'text', 'text': 'Add a scene.'}],
                    },
                }
            ],
        },
    ) as response:
        operations, errors = _collect_assistant_transport_chunks(response)

    app.dependency_overrides.clear()

    tool_activity_values = [
        operation.get('value')
        for operation in operations
        if operation.get('path') == ['toolActivity']
    ]

    tool_activity_failures: list[str] = []
    for value in tool_activity_values:
        if isinstance(value, str) and value == 'Tool execution failed':
            tool_activity_failures.append(value)

    assert tool_activity_failures
    assert all('secret internals' not in payload for payload in tool_activity_failures)
    assert tool_activity_values[-1] is None
    assert errors == ['Internal server error']
