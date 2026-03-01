from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.support import seed_baseline_data


def test_get_projects_returns_seeded_project(client: TestClient, db_session: Session) -> None:
    seed_baseline_data(db_session)

    response = client.get('/api/v1/projects')

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]['name'] == 'Seed Project'


def test_get_project_by_id_returns_404_when_missing(client: TestClient) -> None:
    response = client.get('/api/v1/projects/00000000-0000-0000-0000-000000000000')

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'project_not_found'


def test_create_project_returns_created_project(client: TestClient) -> None:
    response = client.post(
        '/api/v1/projects',
        json={
            'name': 'New Project',
            'description': 'Created from API test',
            'status': 'draft',
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload['id']
    assert payload['name'] == 'New Project'
    assert payload['description'] == 'Created from API test'
    assert payload['status'] == 'draft'
