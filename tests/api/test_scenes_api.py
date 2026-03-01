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


def test_post_scenes_inserts_at_middle_and_renumbers(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    first_insert = client.post(
        f'/api/v1/projects/{ids["project_id"]}/scenes',
        json={'name': 'Scene 2', 'content': {'text': 'Second'}},
    )
    assert first_insert.status_code == 201

    response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/scenes',
        json={'position': 2, 'name': 'Inserted', 'content': {'text': 'Inserted content'}},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload['success'] is True
    assert [scene['sceneNumber'] for scene in payload['scenes']] == [1, 2, 3]
    assert payload['scenes'][1]['name'] == 'Inserted'
    assert payload['scenes'][2]['name'] == 'Scene 2'


def test_post_scenes_clamps_position_to_valid_bounds(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    low_position_response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/scenes',
        json={'position': 0, 'name': 'Prepended', 'content': {'text': 'Start'}},
    )
    assert low_position_response.status_code == 201
    low_position_payload = low_position_response.json()
    assert low_position_payload['scenes'][0]['name'] == 'Prepended'
    assert [scene['sceneNumber'] for scene in low_position_payload['scenes']] == [1, 2]

    high_position_response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/scenes',
        json={'position': 999, 'name': 'Appended', 'content': {'text': 'End'}},
    )
    assert high_position_response.status_code == 201
    high_position_payload = high_position_response.json()
    assert high_position_payload['scenes'][-1]['name'] == 'Appended'
    assert [scene['sceneNumber'] for scene in high_position_payload['scenes']] == [1, 2, 3]


def test_patch_scene_updates_only_target_scene(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    insert_response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/scenes',
        json={'name': 'Scene 2', 'content': {'text': 'Second'}},
    )
    second_scene_id = insert_response.json()['scenes'][1]['id']

    response = client.patch(
        f'/api/v1/projects/{ids["project_id"]}/scenes/{second_scene_id}',
        json={'name': 'Updated Scene 2', 'content': {'text': 'Updated text'}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['name'] == 'Updated Scene 2'
    assert payload['content'] == {'text': 'Updated text'}

    get_response = client.get(f'/api/v1/projects/{ids["project_id"]}/scenes')
    get_payload = get_response.json()
    assert len(get_payload) == 2
    assert get_payload[0]['name'] == 'Scene 1'
    assert get_payload[1]['name'] == 'Updated Scene 2'


def test_delete_scene_renumbers_remaining_scenes(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    client.post(
        f'/api/v1/projects/{ids["project_id"]}/scenes',
        json={'name': 'Scene 2', 'content': {'text': 'Second'}},
    )
    third_insert = client.post(
        f'/api/v1/projects/{ids["project_id"]}/scenes',
        json={'name': 'Scene 3', 'content': {'text': 'Third'}},
    )
    second_scene_id = third_insert.json()['scenes'][1]['id']

    response = client.delete(f'/api/v1/projects/{ids["project_id"]}/scenes/{second_scene_id}')

    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert [scene['sceneNumber'] for scene in payload['scenes']] == [1, 2]
    assert payload['scenes'][1]['name'] == 'Scene 3'


def test_delete_last_scene_creates_default_scene(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.delete(f'/api/v1/projects/{ids["project_id"]}/scenes/{ids["scene_id"]}')

    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert len(payload['scenes']) == 1
    assert payload['scenes'][0]['sceneNumber'] == 1
    assert payload['scenes'][0]['name'] == 'Untitled Scene 1'
    assert payload['scenes'][0]['content'] == {'text': ''}


def test_put_scenes_endpoint_removed(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.put(
        f'/api/v1/projects/{ids["project_id"]}/scenes',
        json={'scenes': []},
    )

    assert response.status_code == 405
