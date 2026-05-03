from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.shot import InvalidShotGenerationError
from ai_video_gen_backend.domain.shot import ShotCreateInput
from ai_video_gen_backend.presentation.api.dependencies import (
    get_generate_shots_use_case,
    get_shot_generation_provider,
)
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
    assert create_first_shot.json()['collectionId'] is None

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
    assert listed_shots[0]['collectionId'] is None

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


def test_generate_shots_endpoint_replaces_scene_shots_with_generated_result(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
) -> None:
    project_id = seed_baseline_data(db_session)['project_id']
    client.post(f'/api/v1/projects/{project_id}/screenplays', json={'title': 'Shots Screenplay'})

    scene_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('generate')},
    )
    scene_id = scene_response.json()['scenes'][0]['id']

    client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots',
        json=_create_shot_payload('Legacy A'),
    )
    client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots',
        json=_create_shot_payload('Legacy B'),
    )

    class FakeShotGenerator:
        def generate_shots(self, scene_content: str) -> list[ShotCreateInput]:
            assert 'scene' in scene_content
            return [
                ShotCreateInput(
                    title='Shot 1',
                    description='Generated first shot',
                    camera_framing='Wide',
                    camera_movement='Static',
                    mood='Calm',
                ),
                ShotCreateInput(
                    title='Shot 2',
                    description='Generated second shot',
                    camera_framing='Close-up',
                    camera_movement='Pan right',
                    mood='Focused',
                ),
                ShotCreateInput(
                    title='Shot 3',
                    description='Generated third shot',
                    camera_framing='Medium',
                    camera_movement='Dolly in',
                    mood='Rising',
                ),
            ]

    app.dependency_overrides[get_shot_generation_provider] = lambda: FakeShotGenerator()
    try:
        response = client.post(
            f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots/generate'
        )
    finally:
        app.dependency_overrides.pop(get_shot_generation_provider, None)

    assert response.status_code == 200
    generated = response.json()
    assert [shot['orderIndex'] for shot in generated] == [1, 2, 3]
    assert [shot['title'] for shot in generated] == ['Shot 1', 'Shot 2', 'Shot 3']

    listed = client.get(f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots').json()
    assert [shot['title'] for shot in listed] == ['Shot 1', 'Shot 2', 'Shot 3']
    assert len(listed) == 3


def test_generate_shots_endpoint_returns_400_on_invalid_generation(
    client: TestClient,
    app: FastAPI,
    db_session: Session,
) -> None:
    project_id = seed_baseline_data(db_session)['project_id']
    client.post(f'/api/v1/projects/{project_id}/screenplays', json={'title': 'Shots Screenplay'})
    scene_id = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('bad')},
    ).json()['scenes'][0]['id']

    class RaisingGenerateShotsUseCase:
        def execute(self, *, project_id: object, scene_id: object) -> None:
            del project_id, scene_id
            raise InvalidShotGenerationError('invalid shot output')

    app.dependency_overrides[get_generate_shots_use_case] = lambda: RaisingGenerateShotsUseCase()
    try:
        response = client.post(
            f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots/generate'
        )
    finally:
        app.dependency_overrides.pop(get_generate_shots_use_case, None)

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'invalid_shot_generation'


def test_generate_shots_endpoint_returns_404_for_missing_scene(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = seed_baseline_data(db_session)['project_id']
    client.post(f'/api/v1/projects/{project_id}/screenplays', json={'title': 'Shots Screenplay'})

    response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/00000000-0000-0000-0000-000000000000/shots/generate'
    )

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'screenplay_scene_not_found'


def test_generate_shots_endpoint_returns_422_for_invalid_scene_id(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = seed_baseline_data(db_session)['project_id']

    response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/not-a-uuid/shots/generate'
    )

    assert response.status_code == 422


def test_ensure_shot_visual_collection_is_idempotent_and_reuses_scene_parent(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = seed_baseline_data(db_session)['project_id']
    client.post(f'/api/v1/projects/{project_id}/screenplays', json={'title': 'Shots Screenplay'})

    scene_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('visual')},
    )
    scene_id = scene_response.json()['scenes'][0]['id']

    first_shot_id = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots',
        json=_create_shot_payload('First shot'),
    ).json()['id']
    second_shot_id = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots',
        json=_create_shot_payload('Second shot'),
    ).json()['id']

    before = client.get(f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots')
    assert before.status_code == 200
    assert [shot['collectionId'] for shot in before.json()] == [None, None]

    first_call = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots/{first_shot_id}/visual-collection'
    )
    assert first_call.status_code == 200
    first_collection = first_call.json()
    assert first_collection['tag'] == 'shot'
    assert first_collection['parentCollectionId'] is not None

    second_call = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots/{first_shot_id}/visual-collection'
    )
    assert second_call.status_code == 200
    assert second_call.json()['id'] == first_collection['id']
    assert second_call.json()['parentCollectionId'] == first_collection['parentCollectionId']

    other_shot_call = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots/{second_shot_id}/visual-collection'
    )
    assert other_shot_call.status_code == 200
    other_collection = other_shot_call.json()
    assert other_collection['id'] != first_collection['id']
    assert other_collection['parentCollectionId'] == first_collection['parentCollectionId']

    after = client.get(f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots')
    assert after.status_code == 200
    linked_ids = [shot['collectionId'] for shot in after.json()]
    assert linked_ids == [first_collection['id'], other_collection['id']]

    collections_response = client.get(f'/api/v1/projects/{project_id}/collections')
    assert collections_response.status_code == 200
    all_collections = collections_response.json()
    scene_collections = [item for item in all_collections if item['tag'] == 'scene']
    shot_collections = [item for item in all_collections if item['tag'] == 'shot']
    assert len(scene_collections) == 1
    assert len(shot_collections) == 2


def test_ensure_shot_visual_collection_does_not_share_collections_across_same_named_scenes(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = seed_baseline_data(db_session)['project_id']
    client.post(f'/api/v1/projects/{project_id}/screenplays', json={'title': 'Shots Screenplay'})

    first_scene_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('shared')},
    )
    first_scene_id = first_scene_response.json()['scenes'][0]['id']
    second_scene_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('shared')},
    )
    second_scene_id = second_scene_response.json()['scenes'][1]['id']

    first_shot_id = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{first_scene_id}/shots',
        json=_create_shot_payload('Same opener'),
    ).json()['id']
    second_shot_id = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{second_scene_id}/shots',
        json=_create_shot_payload('Same opener'),
    ).json()['id']

    first_collection = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{first_scene_id}/shots/{first_shot_id}/visual-collection'
    ).json()
    second_collection = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{second_scene_id}/shots/{second_shot_id}/visual-collection'
    ).json()

    assert first_collection['id'] != second_collection['id']
    assert first_collection['parentCollectionId'] is not None
    assert second_collection['parentCollectionId'] is not None
    assert first_collection['parentCollectionId'] != second_collection['parentCollectionId']

    collections_response = client.get(f'/api/v1/projects/{project_id}/collections')
    assert collections_response.status_code == 200
    all_collections = collections_response.json()
    scene_collections = [item for item in all_collections if item['tag'] == 'scene']
    shot_collections = [item for item in all_collections if item['tag'] == 'shot']
    assert len(scene_collections) == 2
    assert len(shot_collections) == 2


def test_ensure_shot_visual_collection_returns_404_for_missing_shot(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = seed_baseline_data(db_session)['project_id']
    client.post(f'/api/v1/projects/{project_id}/screenplays', json={'title': 'Shots Screenplay'})

    scene_response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes',
        json={'content': _scene_xml('missing-shot')},
    )
    scene_id = scene_response.json()['scenes'][0]['id']

    response = client.post(
        f'/api/v1/projects/{project_id}/screenplays/scenes/{scene_id}/shots/00000000-0000-0000-0000-000000000000/visual-collection'
    )

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'shot_not_found'
