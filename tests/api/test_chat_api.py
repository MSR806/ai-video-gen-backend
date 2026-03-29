from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.chat import ChatMessage
from ai_video_gen_backend.infrastructure.repositories import ChatSqlRepository
from ai_video_gen_backend.presentation.api.dependencies import get_chat_model_provider


class FakeChatModelProvider:
    def generate_reply(self, *, messages: list[ChatMessage]) -> str:
        latest_user_text = ''
        for message in reversed(messages):
            if message.role == 'user':
                latest_user_text = message.text
                break
        return f'Assistant reply to: {latest_user_text}'


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
    assert set(payload.keys()) == {'threadId', 'message'}
    assert isinstance(payload['threadId'], str)
    assert set(payload['message'].keys()) == {'role', 'text', 'images', 'createdAt'}
    assert payload['message']['role'] == 'assistant'
    assert isinstance(payload['message']['text'], str)


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
