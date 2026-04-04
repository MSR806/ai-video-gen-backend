from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.support import seed_baseline_data


def _scene_blocks(prefix: str) -> list[dict[str, str]]:
    return [
        {'id': f'{prefix}-1', 'type': 'slugline', 'text': 'INT. APARTMENT - DAY'},
        {'id': f'{prefix}-2', 'type': 'action', 'text': 'Alex stares out the window.'},
    ]


def test_screenplay_endpoints_happy_path(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)
    project_id = ids['project_id']

    initial_get = client.get(f'/api/v1/projects/{project_id}/screenplays')
    assert initial_get.status_code == 200
    assert initial_get.json() is None

    create_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays',
        json={'title': 'My Screenplay'},
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload['title'] == 'My Screenplay'
    assert create_payload['projectId'] == str(project_id)
    assert create_payload['scenes'] == []

    add_first_scene = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_blocks('a')},
    )
    assert add_first_scene.status_code == 201
    first_scene_payload = add_first_scene.json()
    assert [scene['orderIndex'] for scene in first_scene_payload['scenes']] == [1]

    add_second_scene = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_blocks('b')},
    )
    assert add_second_scene.status_code == 201
    second_scene_payload = add_second_scene.json()
    scene_ids = [scene['id'] for scene in second_scene_payload['scenes']]

    reorder_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/reorder',
        json={'sceneIds': [scene_ids[1], scene_ids[0]]},
    )
    assert reorder_response.status_code == 200
    reordered_payload = reorder_response.json()
    assert [scene['id'] for scene in reordered_payload['scenes']] == [scene_ids[1], scene_ids[0]]
    assert [scene['orderIndex'] for scene in reordered_payload['scenes']] == [1, 2]

    update_scene_response = client.patch(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_ids[1]}',
        json={'content': _scene_blocks('b-updated')},
    )
    assert update_scene_response.status_code == 200
    updated_scene_payload = update_scene_response.json()
    assert updated_scene_payload['content'][0]['id'] == 'b-updated-1'

    update_title_response = client.patch(
        f'/api/v1/projects/{project_id}/screenplays',
        json={'title': 'Updated Screenplay'},
    )
    assert update_title_response.status_code == 200
    assert update_title_response.json()['title'] == 'Updated Screenplay'

    delete_scene_response = client.delete(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_ids[0]}'
    )
    assert delete_scene_response.status_code == 200
    delete_scene_payload = delete_scene_response.json()
    assert len(delete_scene_payload['scenes']) == 1
    assert delete_scene_payload['scenes'][0]['orderIndex'] == 1


def test_screenplay_scene_rejects_duplicate_block_ids(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    project_id = ids['project_id']

    client.post(
        f'/api/v1/projects/{project_id}/screenplays',
        json={'title': 'My Screenplay'},
    )

    response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={
            'content': [
                {'id': 'dup', 'type': 'action', 'text': 'First'},
                {'id': 'dup', 'type': 'dialogue', 'text': 'Second'},
            ]
        },
    )

    assert response.status_code == 422


def test_screenplay_scene_rejects_invalid_block_type(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    project_id = ids['project_id']

    client.post(
        f'/api/v1/projects/{project_id}/screenplays',
        json={'title': 'My Screenplay'},
    )

    response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={
            'content': [
                {'id': 'x-1', 'type': 'unknown', 'text': 'Invalid block type'},
            ]
        },
    )

    assert response.status_code == 422
