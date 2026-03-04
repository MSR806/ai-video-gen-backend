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
    GenerationOperation,
    GenerationRequest,
    ProviderResult,
    ProviderStatus,
    ProviderSubmission,
    ProviderWebhookEvent,
)
from ai_video_gen_backend.presentation.api.dependencies import (
    get_generation_provider,
    get_media_downloader,
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


class FakeMediaDownloader:
    def download(self, url: str, *, max_bytes: int) -> tuple[bytes, str]:
        del max_bytes
        return b'fake-downloaded-content', 'image/png'


class FakeGenerationProvider:
    def __init__(self) -> None:
        self._request_counter = 0
        self._statuses: dict[str, ProviderStatus] = {}
        self._results: dict[str, ProviderResult] = {}

    def resolve_model_key(self, *, operation: GenerationOperation, model_key: str | None) -> str:
        del operation
        return model_key or 'nano_banana_t2i_v1'

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

    def status(self, *, model_key: str, provider_request_id: str) -> ProviderStatus:
        del model_key
        return self._statuses.get(provider_request_id, ProviderStatus(status='FAILED'))

    def result(
        self,
        *,
        model_key: str,
        provider_request_id: str,
    ) -> ProviderResult:
        del model_key
        return self._results[provider_request_id]

    def cancel(self, *, model_key: str, provider_request_id: str) -> None:
        del model_key
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
    *,
    storage: FakeObjectStorage | None = None,
    media_downloader: FakeMediaDownloader | None = None,
) -> FastAPI:
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_generation_provider] = lambda: provider
    if storage is not None:
        app.dependency_overrides[get_object_storage] = lambda: storage
    if media_downloader is not None:
        app.dependency_overrides[get_media_downloader] = lambda: media_downloader
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
    assert payload['parentCollectionId'] is None


def test_create_child_collection_success(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    parent_response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/collections',
        json={
            'name': 'Parent Collection',
            'tag': 'folder',
            'description': 'Parent node',
        },
    )
    assert parent_response.status_code == 201
    parent_id = parent_response.json()['id']

    child_response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/collections',
        json={
            'name': 'Child Collection',
            'tag': 'folder',
            'description': 'Child node',
            'parentCollectionId': parent_id,
        },
    )

    assert child_response.status_code == 201
    payload = child_response.json()
    assert payload['name'] == 'Child Collection'
    assert payload['parentCollectionId'] == parent_id

    list_response = client.get(f'/api/v1/projects/{ids["project_id"]}/collections')
    assert list_response.status_code == 200
    listed = list_response.json()
    listed_child = next(collection for collection in listed if collection['id'] == payload['id'])
    assert listed_child['parentCollectionId'] == parent_id


def test_create_collection_with_unknown_parent_returns_400(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/collections',
        json={
            'name': 'Child Collection',
            'tag': 'folder',
            'description': 'Child node',
            'parentCollectionId': str(uuid4()),
        },
    )

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'invalid_parent_collection'


def test_create_collection_with_cross_project_parent_returns_400(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    project_b_response = client.post(
        '/api/v1/projects',
        json={
            'name': 'Project B',
            'description': 'Project for cross-parent validation',
            'status': 'draft',
        },
    )
    assert project_b_response.status_code == 201
    project_b_id = project_b_response.json()['id']

    parent_response = client.post(
        f'/api/v1/projects/{project_b_id}/collections',
        json={
            'name': 'Project B Parent',
            'tag': 'folder',
            'description': 'Parent in project B',
        },
    )
    assert parent_response.status_code == 201
    parent_id = parent_response.json()['id']

    response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/collections',
        json={
            'name': 'Invalid Child',
            'tag': 'folder',
            'description': 'Should fail',
            'parentCollectionId': parent_id,
        },
    )

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'invalid_parent_collection'


def test_get_collection_items_returns_child_collections(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)

    child_response = client.post(
        f'/api/v1/projects/{ids["project_id"]}/collections',
        json={
            'name': 'Nested Child',
            'tag': 'folder',
            'description': 'Nested child collection',
            'parentCollectionId': str(ids['collection_id']),
        },
    )
    assert child_response.status_code == 201
    child_payload = child_response.json()

    response = client.get(f'/api/v1/collections/{ids["collection_id"]}/items')
    assert response.status_code == 200
    payload = response.json()
    assert len(payload['items']) == 1
    assert len(payload['childCollections']) == 1
    assert payload['childCollections'][0]['id'] == child_payload['id']
    assert payload['childCollections'][0]['parentCollectionId'] == str(ids['collection_id'])


def test_get_collection_items_returns_seeded_items(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.get(f'/api/v1/collections/{ids["collection_id"]}/items')

    assert response.status_code == 200
    payload = response.json()
    items = payload['items']
    assert payload['childCollections'] == []
    assert len(items) == 1
    assert items[0]['name'] == 'Seed Item'
    assert 'storageProvider' not in items[0]
    assert 'storageBucket' not in items[0]
    assert 'storageKey' not in items[0]
    assert 'mimeType' not in items[0]
    assert 'sizeBytes' not in items[0]
    assert 'createdAt' not in items[0]
    assert 'updatedAt' not in items[0]
    assert 'generationSource' not in items[0]


def test_get_collection_item_by_id_returns_item(client: TestClient, db_session: Session) -> None:
    ids = seed_baseline_data(db_session)

    response = client.get(f'/api/v1/collection-items/{ids["item_id"]}')

    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == str(ids['item_id'])
    assert payload['name'] == 'Seed Item'
    assert 'storageProvider' not in payload
    assert 'storageBucket' not in payload
    assert 'storageKey' not in payload
    assert 'mimeType' not in payload
    assert 'sizeBytes' not in payload
    assert 'createdAt' not in payload
    assert 'updatedAt' not in payload
    assert 'generationSource' not in payload


def test_get_collection_item_by_id_returns_404(client: TestClient) -> None:
    response = client.get(f'/api/v1/collection-items/{uuid4()}')

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'collection_item_not_found'


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
    assert items_response.json()['items'] == []


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
    assert any(item['id'] == item_id for item in items_response.json()['items'])


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
    assert payload['id']
    assert payload['status'] == 'GENERATING'
    assert payload['jobId']
    assert payload['url'] is None

    items_response = client.get(f'/api/v1/collections/{ids["collection_id"]}/items')
    assert items_response.status_code == 200
    generated_item = next(
        item for item in items_response.json()['items'] if item['id'] == payload['id']
    )
    assert generated_item['jobId'] == payload['jobId']


def test_get_generation_job_returns_404_when_missing(client: TestClient) -> None:
    response = client.get('/api/v1/generation-jobs/00000000-0000-0000-0000-000000000000')

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'generation_job_not_found'


def test_generation_webhook_invalid_token_returns_401(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_provider = FakeGenerationProvider()
    app = _override_generation_dependency(
        client,
        fake_provider,
        media_downloader=FakeMediaDownloader(),
    )

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
        app.dependency_overrides.pop(get_media_downloader, None)

    assert response.status_code == 401
    assert response.json()['error']['code'] == 'unauthorized_webhook'


def test_generation_webhook_failure_marks_placeholder_item_failed(
    client: TestClient,
    db_session: Session,
) -> None:
    ids = seed_baseline_data(db_session)
    fake_provider = FakeGenerationProvider()
    app = _override_generation_dependency(
        client,
        fake_provider,
        media_downloader=FakeMediaDownloader(),
    )

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
        item_id = submit.json()['id']

        webhook = client.post(
            '/api/v1/provider-webhooks/fal?token=',
            json={'request_id': 'req-1', 'status': 'ERROR'},
        )
    finally:
        app.dependency_overrides.pop(get_generation_provider, None)
        app.dependency_overrides.pop(get_media_downloader, None)

    assert webhook.status_code == 200
    assert webhook.json()['handled'] is True

    items_response = client.get(f'/api/v1/collections/{ids["collection_id"]}/items')
    assert items_response.status_code == 200
    generated_item = next(item for item in items_response.json()['items'] if item['id'] == item_id)
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
