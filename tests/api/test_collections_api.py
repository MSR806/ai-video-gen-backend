from __future__ import annotations

from typing import BinaryIO, cast
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.collection_item import (
    StorageError,
    StoredObject,
    VideoThumbnailGenerationError,
)
from ai_video_gen_backend.domain.generation import (
    GenerationRequest,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
)
from ai_video_gen_backend.presentation.api.dependencies import (
    get_generation_provider,
    get_object_storage,
    get_video_thumbnail_generator,
)
from tests.support import seed_baseline_data


class FakeObjectStorage:
    def __init__(self, *, fail_on_delete: bool = False) -> None:
        self.uploaded_keys: list[str] = []
        self.deleted_keys: list[str] = []
        self.fail_on_delete = fail_on_delete

    def upload_object(
        self,
        *,
        key: str,
        content_type: str,
        body: BinaryIO,
        size_bytes: int,
    ) -> StoredObject:
        body.seek(0)
        self.uploaded_keys.append(key)
        return StoredObject(
            provider='s3',
            bucket='ai-video-gen-media',
            key=key,
            url=f'http://localhost:9000/ai-video-gen-media/{key}',
            mime_type=content_type,
            size_bytes=size_bytes,
        )

    def delete_object(self, *, key: str) -> None:
        if self.fail_on_delete:
            raise StorageError('delete failed')
        self.deleted_keys.append(key)


class FakeVideoThumbnailGenerator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def extract_first_frame(self, *, video_stream: BinaryIO) -> bytes:
        if self.fail:
            raise VideoThumbnailGenerationError('ffmpeg failed')

        video_stream.seek(0)
        return b'thumbnail-jpeg'


class FakeGenerationProvider:
    def __init__(self) -> None:
        self._request_counter = 0
        self._statuses: dict[str, ProviderStatus] = {}
        self._results: dict[str, ProviderResult] = {}

    def submit(self, request: GenerationRequest, *, webhook_url: str) -> ProviderSubmission:
        del request, webhook_url
        self._request_counter += 1
        request_id = f'req-{self._request_counter}'
        self._statuses[request_id] = ProviderStatus(status='IN_PROGRESS')
        self._results[request_id] = ProviderResult(
            status='FAILED',
            output_url=None,
            raw_response={'status': 'ERROR'},
            error_message='not-ready',
        )
        return ProviderSubmission(provider_request_id=request_id)

    def status(self, *, endpoint_id: str, provider_request_id: str) -> ProviderStatus:
        del endpoint_id
        return self._statuses.get(provider_request_id, ProviderStatus(status='FAILED'))

    def result(
        self,
        *,
        endpoint_id: str,
        provider_request_id: str,
        model_key: str | None = None,
    ) -> ProviderResult:
        del endpoint_id, model_key
        return self._results[provider_request_id]

    def cancel(self, *, endpoint_id: str, provider_request_id: str) -> None:
        del endpoint_id
        self._statuses[provider_request_id] = ProviderStatus(status='CANCELLED')

    def parse_webhook(self, payload: dict[str, object]) -> ProviderWebhookEvent | None:
        request_id = payload.get('request_id')
        status = payload.get('status')
        if not isinstance(request_id, str) or not isinstance(status, str):
            return None
        if status.upper() == 'OK':
            return ProviderWebhookEvent(
                provider_request_id=request_id,
                status='SUCCEEDED',
                output_url='https://example.com/generated.png',
                raw_response=payload,
            )
        return ProviderWebhookEvent(
            provider_request_id=request_id,
            status='FAILED',
            output_url=None,
            raw_response=payload,
            error_message='provider error',
        )


def _override_upload_dependencies(
    client: TestClient,
    storage: FakeObjectStorage,
    thumbnail_generator: FakeVideoThumbnailGenerator | None = None,
) -> FastAPI:
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_object_storage] = lambda: storage
    if thumbnail_generator is not None:
        app.dependency_overrides[get_video_thumbnail_generator] = lambda: thumbnail_generator
    return app


def _override_generation_dependency(
    client: TestClient,
    provider: FakeGenerationProvider,
) -> FastAPI:
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_generation_provider] = lambda: provider
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


def test_delete_collection_item_success(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.delete(f'/api/v1/collections/{ids["collection_id"]}/items/{ids["item_id"]}')

    assert response.status_code == 204

    items_response = client.get(f'/api/v1/collections/{ids["collection_id"]}/items')
    assert items_response.status_code == 200
    assert items_response.json() == []


def test_delete_collection_item_not_found_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    response = client.delete(f'/api/v1/collections/{ids["collection_id"]}/items/{uuid4()}')

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'collection_item_not_found'


def test_delete_collection_item_removes_storage_object(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_storage = FakeObjectStorage()
    app = _override_upload_dependencies(client, fake_storage)

    try:
        upload_response = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/upload',
            data={'projectId': str(ids['project_id'])},
            files={'file': ('upload.jpg', b'fake-image-bytes', 'image/jpeg')},
        )
        assert upload_response.status_code == 201
        item_id = upload_response.json()['id']

        delete_response = client.delete(
            f'/api/v1/collections/{ids["collection_id"]}/items/{item_id}'
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)

    assert delete_response.status_code == 204
    assert set(fake_storage.deleted_keys) == set(fake_storage.uploaded_keys)


def test_delete_collection_item_storage_failure_returns_502(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_storage = FakeObjectStorage(fail_on_delete=True)
    app = _override_upload_dependencies(client, fake_storage)

    try:
        upload_response = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/upload',
            data={'projectId': str(ids['project_id'])},
            files={'file': ('upload.jpg', b'fake-image-bytes', 'image/jpeg')},
        )
        assert upload_response.status_code == 201
        item_id = upload_response.json()['id']

        delete_response = client.delete(
            f'/api/v1/collections/{ids["collection_id"]}/items/{item_id}'
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)

    assert delete_response.status_code == 502
    assert delete_response.json()['error']['code'] == 'storage_delete_failed'

    items_response = client.get(f'/api/v1/collections/{ids["collection_id"]}/items')
    assert items_response.status_code == 200
    assert any(item['id'] == item_id for item in items_response.json())


def test_generate_collection_item_returns_async_job(
    client: TestClient, db_session: Session
) -> None:
    ids = seed_baseline_data(db_session)
    fake_provider = FakeGenerationProvider()
    app = _override_generation_dependency(client, fake_provider)

    try:
        response = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/generate',
            json={
                'projectId': str(ids['project_id']),
                'operation': 'TEXT_TO_IMAGE',
                'prompt': 'cinematic wide shot',
                'aspectRatio': 'LANDSCAPE',
            },
        )
    finally:
        app.dependency_overrides.pop(get_generation_provider, None)

    assert response.status_code == 202
    payload = response.json()
    assert payload['jobId']
    assert payload['itemId']
    assert payload['status'] in {'QUEUED', 'IN_PROGRESS'}


def test_get_generation_job_returns_404_when_missing(client: TestClient) -> None:
    response = client.get('/api/v1/generation-jobs/00000000-0000-0000-0000-000000000000')

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'generation_job_not_found'


def test_list_generation_jobs_requires_scope_filter(client: TestClient) -> None:
    response = client.get('/api/v1/generation-jobs')

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'validation_error'


def test_list_generation_jobs_by_collection_and_status(
    client: TestClient, db_session: Session
) -> None:
    ids = seed_baseline_data(db_session)
    fake_provider = FakeGenerationProvider()
    app = _override_generation_dependency(client, fake_provider)

    try:
        submit = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/generate',
            json={
                'projectId': str(ids['project_id']),
                'operation': 'TEXT_TO_IMAGE',
                'prompt': 'portrait',
            },
        )
        assert submit.status_code == 202

        response = client.get(
            '/api/v1/generation-jobs',
            params=[
                ('collectionId', str(ids['collection_id'])),
                ('status', 'QUEUED'),
                ('status', 'IN_PROGRESS'),
            ],
        )
    finally:
        app.dependency_overrides.pop(get_generation_provider, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    assert all(job['collectionId'] == str(ids['collection_id']) for job in payload)
    assert all(job['status'] in {'QUEUED', 'IN_PROGRESS'} for job in payload)


def test_generation_webhook_invalid_token_returns_401(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_provider = FakeGenerationProvider()
    app = _override_generation_dependency(client, fake_provider)

    try:
        submit = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/generate',
            json={
                'projectId': str(ids['project_id']),
                'operation': 'TEXT_TO_IMAGE',
                'prompt': 'sunset',
            },
        )
        assert submit.status_code == 202
        response = client.post(
            '/api/v1/provider-webhooks/fal?token=invalid',
            json={'request_id': 'req-1', 'status': 'ERROR'},
        )
    finally:
        app.dependency_overrides.pop(get_generation_provider, None)

    assert response.status_code == 401
    assert response.json()['error']['code'] == 'unauthorized_webhook'


def test_generation_webhook_failure_marks_placeholder_item_failed(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_provider = FakeGenerationProvider()
    app = _override_generation_dependency(client, fake_provider)

    try:
        submit = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/generate',
            json={
                'projectId': str(ids['project_id']),
                'operation': 'TEXT_TO_IMAGE',
                'prompt': 'sunset',
            },
        )
        assert submit.status_code == 202
        item_id = submit.json()['itemId']

        webhook = client.post(
            '/api/v1/provider-webhooks/fal?token=',
            json={'request_id': 'req-1', 'status': 'ERROR'},
        )
    finally:
        app.dependency_overrides.pop(get_generation_provider, None)

    assert webhook.status_code == 200
    assert webhook.json()['handled'] is True

    items_response = client.get(f'/api/v1/collections/{ids["collection_id"]}/items')
    assert items_response.status_code == 200
    generated_item = next(item for item in items_response.json() if item['id'] == item_id)
    assert generated_item['status'] == 'FAILED'


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
    app = _override_upload_dependencies(client, fake_storage)

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
    assert payload['metadata']['thumbnailUrl'] == payload['url']


def test_upload_video_collection_item_generates_thumbnail(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_storage = FakeObjectStorage()
    fake_thumbnail_generator = FakeVideoThumbnailGenerator()
    app = _override_upload_dependencies(client, fake_storage, fake_thumbnail_generator)

    try:
        response = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/upload',
            data={'projectId': str(ids['project_id'])},
            files={'file': ('upload.mp4', b'fake-video-bytes', 'video/mp4')},
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_video_thumbnail_generator, None)

    assert response.status_code == 201
    payload = response.json()
    assert payload['mediaType'] == 'video'
    assert payload['metadata']['thumbnailUrl']
    assert payload['metadata']['thumbnailUrl'] != payload['url']
    assert len(fake_storage.uploaded_keys) == 2
    assert fake_storage.uploaded_keys[1].endswith('-thumb.jpg')


def test_upload_video_collection_item_thumbnail_failure_keeps_upload(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_storage = FakeObjectStorage()
    failing_thumbnail_generator = FakeVideoThumbnailGenerator(fail=True)
    app = _override_upload_dependencies(client, fake_storage, failing_thumbnail_generator)

    try:
        response = client.post(
            f'/api/v1/collections/{ids["collection_id"]}/items/upload',
            data={'projectId': str(ids['project_id'])},
            files={'file': ('upload.mp4', b'fake-video-bytes', 'video/mp4')},
        )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)
        app.dependency_overrides.pop(get_video_thumbnail_generator, None)

    assert response.status_code == 201
    payload = response.json()
    assert payload['mediaType'] == 'video'
    assert payload['metadata']['thumbnailUrl'] == ''
    assert len(fake_storage.uploaded_keys) == 1


def test_upload_collection_item_invalid_mime_returns_400(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_storage = FakeObjectStorage()
    app = _override_upload_dependencies(client, fake_storage)

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
    app = _override_upload_dependencies(client, fake_storage)

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
    app = _override_upload_dependencies(client, fake_storage)

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
