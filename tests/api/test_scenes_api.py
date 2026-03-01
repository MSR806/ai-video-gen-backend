from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.support import seed_baseline_data


def test_get_scenes_returns_seeded_scenes(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.get(f'/api/v1/projects/{ids["project_id"]}/scenes')

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]['sceneNumber'] == 1


def test_put_scenes_replaces_scenes_and_normalizes_numbers(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    response = client.put(
        f'/api/v1/projects/{ids["project_id"]}/scenes',
        json={
            'scenes': [
                {'name': 'First', 'sceneNumber': 99, 'body': 'Body A'},
                {'name': '', 'body': 'Body B'},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['scenes'][0]['sceneNumber'] == 1
    assert payload['scenes'][1]['sceneNumber'] == 2
    assert payload['scenes'][1]['name'] == 'Untitled Scene 2'

    get_response = client.get(f'/api/v1/projects/{ids["project_id"]}/scenes')
    get_payload = get_response.json()
    assert len(get_payload) == 2
