from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_video_gen_backend.infrastructure.db.models import ProjectModel
from tests.support import seed_baseline_data


def test_get_projects_returns_seeded_project(client: TestClient, db_session: Session) -> None:
    seed_baseline_data(db_session)

    response = client.get('/api/v1/projects')

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]['name'] == 'Seed Project'
    assert payload[0]['style'] is None
    assert payload[0]['aspectRatio'] == '16:9'


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
    assert payload['style'] is None
    assert payload['aspectRatio'] == '16:9'
    assert payload['status'] == 'draft'


def test_create_project_persists_style_and_aspect_ratio(client: TestClient) -> None:
    response = client.post(
        '/api/v1/projects',
        json={
            'name': 'Styled Project',
            'description': 'Created with style and ratio',
            'style': 'high contrast comic panels',
            'aspectRatio': '9:16',
            'status': 'in-progress',
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload['style'] == 'high contrast comic panels'
    assert payload['aspectRatio'] == '9:16'
    assert payload['status'] == 'in-progress'


def test_get_project_defaults_aspect_ratio_when_db_value_is_null(
    client: TestClient,
    db_session: Session,
) -> None:
    project = ProjectModel(
        name='Legacy Project',
        description='Null aspect ratio row',
        style=None,
        aspect_ratio=None,
        status='draft',
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    response = client.get(f'/api/v1/projects/{project.id}')

    assert response.status_code == 200
    payload = response.json()
    assert payload['style'] is None
    assert payload['aspectRatio'] == '16:9'


def test_patch_project_updates_style_and_aspect_ratio_preserving_other_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    project = ProjectModel(
        name='Original Project',
        description='Original description',
        style='minimalist',
        aspect_ratio='16:9',
        status='in-progress',
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    response = client.patch(
        f'/api/v1/projects/{project.id}',
        json={
            'style': 'ink wash',
            'aspectRatio': '1:1',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == str(project.id)
    assert payload['name'] == 'Original Project'
    assert payload['description'] == 'Original description'
    assert payload['status'] == 'in-progress'
    assert payload['style'] == 'ink wash'
    assert payload['aspectRatio'] == '1:1'


def test_patch_project_returns_404_when_missing(client: TestClient) -> None:
    response = client.patch(
        '/api/v1/projects/00000000-0000-0000-0000-000000000000',
        json={'style': 'paper cutout'},
    )

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'project_not_found'


def test_patch_project_forbids_extra_fields(client: TestClient, db_session: Session) -> None:
    project = ProjectModel(
        name='Strict Project',
        description='Validation check',
        style=None,
        aspect_ratio='16:9',
        status='draft',
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    response = client.patch(
        f'/api/v1/projects/{project.id}',
        json={
            'style': 'anime line art',
            'unknownField': 'nope',
        },
    )

    assert response.status_code == 422
