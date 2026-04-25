from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.support import seed_baseline_data


def _scene_xml(prefix: str) -> str:
    return (
        '<scene>'
        f'<slugline>INT. STUDIO {prefix.upper()} - DAY</slugline>'
        '<action>Camera setup in progress.</action>'
        '</scene>'
    )


def _create_shot_payload(title: str) -> dict[str, str]:
    return {
        'title': title,
        'description': f'{title} description',
        'cameraFraming': 'Wide',
        'cameraMovement': 'Track right',
        'mood': 'Energetic',
    }


def test_shot_endpoints_happy_path(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)
    project_id = ids['project_id']

    create_screenplay = client.post(
        f'/api/v1/projects/{project_id}/screenplays',
        json={'title': 'Shots Screenplay'},
    )
    assert create_screenplay.status_code == 201

    first_scene_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('a')},
    )
    assert first_scene_response.status_code == 201
    first_scene_id = first_scene_response.json()['scenes'][0]['id']

    second_scene_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('b')},
    )
    assert second_scene_response.status_code == 201
    second_scene_id = second_scene_response.json()['scenes'][1]['id']

    create_first_shot = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{first_scene_id}/shots',
        json=_create_shot_payload('Shot A'),
    )
    assert create_first_shot.status_code == 201
    first_shot_id = create_first_shot.json()['id']

    create_second_shot = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{first_scene_id}/shots',
        json=_create_shot_payload('Shot B'),
    )
    assert create_second_shot.status_code == 201
    second_shot_id = create_second_shot.json()['id']

    create_third_shot = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{second_scene_id}/shots',
        json=_create_shot_payload('Shot C'),
    )
    assert create_third_shot.status_code == 201

    list_response = client.get(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{first_scene_id}/shots'
    )
    assert list_response.status_code == 200
    listed_shots = list_response.json()
    assert [shot['orderIndex'] for shot in listed_shots] == [1, 2]
    assert listed_shots[0]['title'] == 'Shot A'

    reorder_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{first_scene_id}/shots/reorder',
        json={'shotIds': [second_shot_id, first_shot_id]},
    )
    assert reorder_response.status_code == 200
    assert [shot['id'] for shot in reorder_response.json()] == [second_shot_id, first_shot_id]

    update_response = client.patch(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{first_scene_id}/shots/{second_shot_id}',
        json={'mood': 'Suspenseful'},
    )
    assert update_response.status_code == 200
    assert update_response.json()['mood'] == 'Suspenseful'

    delete_response = client.delete(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{first_scene_id}/shots/{first_shot_id}'
    )
    assert delete_response.status_code == 204

    screenplay_response = client.get(f'/api/v1/projects/{project_id}/screenplays')
    assert screenplay_response.status_code == 200
    scenes = screenplay_response.json()['scenes']
    assert scenes[0]['shotCount'] == 1
    assert scenes[1]['shotCount'] == 1


def test_shot_endpoints_return_404_when_scene_does_not_belong_to_project(
    client: TestClient,
    db_session: Session,
) -> None:
    project_a = seed_baseline_data(db_session)['project_id']
    project_b = seed_baseline_data(db_session)['project_id']

    client.post(f'/api/v1/projects/{project_a}/screenplays', json={'title': 'A'})
    client.post(f'/api/v1/projects/{project_b}/screenplays', json={'title': 'B'})

    scene_b_response = client.post(
        f'/api/v1/projects/{project_b}/screenplays/scenes',
        json={'content': _scene_xml('b')},
    )
    scene_b_id = scene_b_response.json()['scenes'][0]['id']

    response = client.get(f'/api/v1/projects/{project_a}/screenplays/scenes/{scene_b_id}/shots')

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'screenplay_scene_not_found'


def test_shot_reorder_rejects_invalid_order(client: TestClient, db_session: Session) -> None:
    project_id = seed_baseline_data(db_session)['project_id']
    client.post(f'/api/v1/projects/{project_id}/screenplays', json={'title': 'Shots Screenplay'})

    scene_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('a')},
    )
    scene_id = scene_response.json()['scenes'][0]['id']

    first = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots',
        json=_create_shot_payload('Shot A'),
    ).json()
    second = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots',
        json=_create_shot_payload('Shot B'),
    ).json()

    response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots/reorder',
        json={'shotIds': [first['id'], first['id']]},
    )
    assert response.status_code == 422

    response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots/reorder',
        json={'shotIds': [first['id']]},
    )
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'invalid_shot_order'
    assert second['id']


def test_shot_request_schema_is_strict(client: TestClient, db_session: Session) -> None:
    project_id = seed_baseline_data(db_session)['project_id']
    client.post(f'/api/v1/projects/{project_id}/screenplays', json={'title': 'Shots Screenplay'})

    scene_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('a')},
    )
    scene_id = scene_response.json()['scenes'][0]['id']

    response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots',
        json={
            **_create_shot_payload('Shot A'),
            'status': 'draft',
        },
    )

    assert response.status_code == 422
