from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.support import seed_baseline_data


def test_get_collection_items_returns_seeded_items(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.get(f'/api/v1/collections/{ids["collection_id"]}/items')

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]['name'] == 'Seed Item'


def test_create_collection_item_success(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.post(
        f'/api/v1/collections/{ids["collection_id"]}/items',
        json={
            'projectId': str(ids['project_id']),
            'mediaType': 'image',
            'name': 'Created Item',
            'description': 'Created from API test',
            'url': 'https://example.com/created.jpg',
            'metadata': {'width': 100, 'height': 200, 'format': 'jpg'},
            'generationSource': 'upload',
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload['name'] == 'Created Item'
    assert payload['mediaType'] == 'image'


def test_generate_collection_item_stub(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.post(
        f'/api/v1/collections/{ids["collection_id"]}/items/generate',
        json={
            'prompt': 'cinematic wide shot',
            'aspectRatio': 'landscape',
            'mediaType': 'video',
            'projectId': str(ids['project_id']),
            'resolution': '2k',
            'batchSize': 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['format'] == 'mp4'
    assert payload['duration'] == 10


def test_create_collection_item_project_mismatch_returns_400(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    response = client.post(
        f'/api/v1/collections/{ids["collection_id"]}/items',
        json={
            'projectId': '00000000-0000-0000-0000-000000000000',
            'mediaType': 'image',
            'name': 'Invalid Item',
            'description': 'Invalid relation',
            'url': 'https://example.com/invalid.jpg',
            'metadata': {'width': 100, 'height': 200, 'format': 'jpg'},
            'generationSource': 'upload',
        },
    )

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'collection_project_mismatch'
