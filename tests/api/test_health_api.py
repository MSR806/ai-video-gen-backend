from __future__ import annotations

from fastapi.testclient import TestClient

from ai_video_gen_backend.config.settings import Settings
from ai_video_gen_backend.main import create_app


def test_live_health_endpoint(client: TestClient) -> None:
    response = client.get('/health/live')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_ready_health_endpoint_returns_ready_when_db_is_up(client: TestClient) -> None:
    response = client.get('/health/ready')

    assert response.status_code == 200
    assert response.json() == {'status': 'ready'}


def test_ready_health_endpoint_returns_503_when_db_is_down() -> None:
    app = create_app(
        Settings(
            app_env='test',
            log_level='INFO',
            api_v1_prefix='/api/v1',
            database_url='postgresql+psycopg://app:app@127.0.0.1:1/ai_video_gen',
        )
    )

    with TestClient(app) as client:
        response = client.get('/health/ready')

    assert response.status_code == 503
    assert response.json()['error']['code'] == 'database_unavailable'
