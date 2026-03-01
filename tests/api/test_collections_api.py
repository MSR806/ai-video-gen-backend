from __future__ import annotations

from typing import BinaryIO, cast
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.collection_item import StoredObject
from ai_video_gen_backend.presentation.api.dependencies import get_object_storage
from tests.support import seed_baseline_data


class FakeObjectStorage:
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    def upload_object(
        self,
        *,
        key: str,
        content_type: str,
        body: BinaryIO,
        size_bytes: int,
    ) -> StoredObject:
        body.seek(0)
        return StoredObject(
            provider='s3',
            bucket='ai-video-gen-media',
            key=key,
            url=f'http://localhost:9000/ai-video-gen-media/{key}',
            mime_type=content_type,
            size_bytes=size_bytes,
        )

    def delete_object(self, *, key: str) -> None:
        self.deleted_keys.append(key)


def _override_storage(client: TestClient, storage: FakeObjectStorage) -> FastAPI:
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_object_storage] = lambda: storage
    return app


def test_create_collection_success(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/collections',
        json={
            'name': 'New Collection',
            'tag': 'reference',
            'description': 'Created via API',
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload['name'] == 'New Collection'
    assert payload['tag'] == 'reference'
    assert payload['projectId'] == str(ids['project_id'])


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


def test_upload_collection_item_success(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)
    fake_storage = FakeObjectStorage()
    app = _override_storage(client, fake_storage)

    try:
        response = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/upload',
            data={
                'projectId': str(ids['project_id']),
                'name': 'Uploaded Item',
                'description': 'Uploaded from multipart',
                'metadata': '{"width":640,"height":360,"format":"jpg","thumbnailUrl":"thumb"}',
            },
            files={'file': ('upload.jpg', b'fake-image-bytes', 'image/jpeg')},
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)

    assert response.status_code == 201
    payload = response.json()
    assert payload['name'] == 'Uploaded Item'
    assert payload['mediaType'] == 'image'
    assert payload['storageProvider'] == 's3'
    assert payload['storageBucket'] == 'ai-video-gen-media'
    assert payload['mimeType'] == 'image/jpeg'
    assert payload['sizeBytes'] == len(b'fake-image-bytes')
    assert payload['url'].startswith('http://localhost:9000/ai-video-gen-media/projects/')


def test_upload_collection_item_invalid_mime_returns_400(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_storage = FakeObjectStorage()
    app = _override_storage(client, fake_storage)

    try:
        response = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/upload',
            data={'projectId': str(ids['project_id'])},
            files={'file': ('notes.txt', b'plain text', 'text/plain')},
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'unsupported_media_type'


def test_upload_collection_item_missing_file_returns_400(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    response = client.post(
        f'/api/v1/collections/{ids["collection_id"]}/items/upload',
        data={'projectId': str(ids['project_id'])},
    )

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'validation_error'


def test_upload_collection_item_invalid_project_id_returns_400(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_storage = FakeObjectStorage()
    app = _override_storage(client, fake_storage)

    try:
        response = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/upload',
            data={'projectId': 'invalid-uuid'},
            files={'file': ('upload.jpg', b'fake-image-bytes', 'image/jpeg')},
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'validation_error'


def test_upload_collection_item_project_mismatch_returns_400(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_storage = FakeObjectStorage()
    app = _override_storage(client, fake_storage)

    try:
        response = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/upload',
            data={'projectId': str(uuid4())},
            files={'file': ('upload.jpg', b'fake-image-bytes', 'image/jpeg')},
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'collection_project_mismatch'
