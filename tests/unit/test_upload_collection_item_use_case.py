from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.collection_item import (
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    UploadCollectionItemUseCase,
)
from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    CollectionItemCreationPayload,
    CollectionItemGenerationParams,
    GeneratedCollectionItem,
    JsonValue,
    StoredObject,
    VideoThumbnailGenerationError,
)


class FakeCollectionItemRepository:
    def __init__(self, *, fail_on_create: bool = False) -> None:
        self.fail_on_create = fail_on_create
        self.created_payload: CollectionItemCreationPayload | None = None

    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]:
        del collection_id
        return []

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None:
        del item_id
        return None

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem:
        self.created_payload = payload
        if self.fail_on_create:
            raise RuntimeError('db failure')

        return CollectionItem(
            id=uuid4(),
            project_id=payload.project_id,
            collection_id=payload.collection_id,
            media_type=payload.media_type,
            status=payload.status,
            name=payload.name,
            description=payload.description,
            url=payload.url,
            metadata=payload.metadata,
            generation_source=payload.generation_source,
            generation_error_message=payload.generation_error_message,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            storage_provider=payload.storage_provider,
            storage_bucket=payload.storage_bucket,
            storage_key=payload.storage_key,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
        )

    def delete_item(self, item_id: UUID) -> bool:
        del item_id
        return False

    def assign_job_id(self, *, item_id: UUID, job_id: UUID) -> CollectionItem | None:
        del item_id, job_id
        return None

    def mark_generated_item_ready(
        self,
        *,
        item_id: UUID,
        url: str,
        metadata: dict[str, JsonValue],
        storage_provider: str | None,
        storage_bucket: str | None,
        storage_key: str | None,
        mime_type: str | None,
        size_bytes: int | None,
    ) -> CollectionItem | None:
        del (
            item_id,
            url,
            metadata,
            storage_provider,
            storage_bucket,
            storage_key,
            mime_type,
            size_bytes,
        )
        return None

    def mark_generated_item_failed(
        self, *, item_id: UUID, error_message: str
    ) -> CollectionItem | None:
        del item_id, error_message
        return None

    def generate_item(self, params: CollectionItemGenerationParams) -> GeneratedCollectionItem:
        del params
        raise NotImplementedError


class FakeObjectStorage:
    def __init__(self) -> None:
        self.uploaded: list[StoredObject] = []
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
        stored = StoredObject(
            provider='s3',
            bucket='uploads',
            key=key,
            url=f'https://storage.test/uploads/{key}',
            mime_type=content_type,
            size_bytes=size_bytes,
        )
        self.uploaded.append(stored)
        return stored

    def delete_object(self, *, key: str) -> None:
        self.deleted_keys.append(key)


class FakeVideoThumbnailGenerator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def extract_first_frame(self, *, video_stream: BinaryIO) -> bytes:
        if self.fail:
            raise VideoThumbnailGenerationError('thumbnail extraction failed')

        video_stream.seek(0)
        return b'jpeg-thumbnail'


def test_upload_collection_item_video_happy_path_generates_thumbnail_and_defaults() -> None:
    repository = FakeCollectionItemRepository()
    object_storage = FakeObjectStorage()
    thumbnail_generator = FakeVideoThumbnailGenerator()
    use_case = UploadCollectionItemUseCase(
        repository,
        object_storage,
        thumbnail_generator,
        max_upload_size_bytes=1024,
        allowed_mime_prefixes=('image/', 'video/'),
    )
    project_id = uuid4()
    collection_id = uuid4()

    result = use_case.execute(
        project_id=project_id,
        collection_id=collection_id,
        filename='My Clip!!.MP4',
        content_type='video/mp4',
        file_stream=BytesIO(b'video-bytes'),
        size_bytes=11,
        name=None,
        description='',
        metadata=None,
    )

    assert repository.created_payload is not None
    created_payload = repository.created_payload
    assert created_payload.media_type == 'video'
    assert created_payload.name == 'My-Clip'
    assert created_payload.storage_provider == 's3'
    assert created_payload.storage_bucket == 'uploads'
    assert created_payload.storage_key is not None
    assert created_payload.storage_key.startswith(
        f'projects/{project_id}/collections/{collection_id}/'
    )
    assert created_payload.url is not None
    assert created_payload.url.startswith('https://storage.test/uploads/projects/')
    assert len(object_storage.uploaded) == 2
    assert object_storage.uploaded[1].key.endswith('-thumb.jpg')
    assert created_payload.metadata['thumbnailUrl'] == object_storage.uploaded[1].url
    assert created_payload.metadata['duration'] == 0
    assert created_payload.metadata['sizeBytes'] == 11
    assert result.storage_key == created_payload.storage_key


def test_upload_collection_item_image_thumbnail_uses_original_url() -> None:
    repository = FakeCollectionItemRepository()
    object_storage = FakeObjectStorage()
    thumbnail_generator = FakeVideoThumbnailGenerator()
    use_case = UploadCollectionItemUseCase(
        repository,
        object_storage,
        thumbnail_generator,
        max_upload_size_bytes=1024,
        allowed_mime_prefixes=('image/', 'video/'),
    )

    result = use_case.execute(
        project_id=uuid4(),
        collection_id=uuid4(),
        filename='shot.png',
        content_type='image/png',
        file_stream=BytesIO(b'png'),
        size_bytes=3,
        name='Shot',
        description='',
        metadata=None,
    )

    assert repository.created_payload is not None
    created_payload = repository.created_payload
    assert created_payload.media_type == 'image'
    assert len(object_storage.uploaded) == 1
    assert created_payload.metadata['thumbnailUrl'] == created_payload.url
    assert result.url == created_payload.url


def test_upload_collection_item_video_thumbnail_failure_continues_with_empty_thumbnail() -> None:
    repository = FakeCollectionItemRepository()
    object_storage = FakeObjectStorage()
    thumbnail_generator = FakeVideoThumbnailGenerator(fail=True)
    use_case = UploadCollectionItemUseCase(
        repository,
        object_storage,
        thumbnail_generator,
        max_upload_size_bytes=1024,
        allowed_mime_prefixes=('image/', 'video/'),
    )

    use_case.execute(
        project_id=uuid4(),
        collection_id=uuid4(),
        filename='clip.mp4',
        content_type='video/mp4',
        file_stream=BytesIO(b'video'),
        size_bytes=5,
        name='Clip',
        description='',
        metadata=None,
    )

    assert repository.created_payload is not None
    created_payload = repository.created_payload
    assert created_payload.media_type == 'video'
    assert len(object_storage.uploaded) == 1
    assert created_payload.metadata['thumbnailUrl'] == ''


def test_upload_collection_item_rejects_unsupported_mime_type() -> None:
    repository = FakeCollectionItemRepository()
    object_storage = FakeObjectStorage()
    thumbnail_generator = FakeVideoThumbnailGenerator()
    use_case = UploadCollectionItemUseCase(
        repository,
        object_storage,
        thumbnail_generator,
        max_upload_size_bytes=1024,
        allowed_mime_prefixes=('image/', 'video/'),
    )

    with pytest.raises(UnsupportedMediaTypeError):
        use_case.execute(
            project_id=uuid4(),
            collection_id=uuid4(),
            filename='notes.txt',
            content_type='text/plain',
            file_stream=BytesIO(b'text'),
            size_bytes=4,
            name='Notes',
            description='',
            metadata=None,
        )


def test_upload_collection_item_rejects_payload_larger_than_limit() -> None:
    repository = FakeCollectionItemRepository()
    object_storage = FakeObjectStorage()
    thumbnail_generator = FakeVideoThumbnailGenerator()
    use_case = UploadCollectionItemUseCase(
        repository,
        object_storage,
        thumbnail_generator,
        max_upload_size_bytes=5,
        allowed_mime_prefixes=('image/', 'video/'),
    )

    with pytest.raises(PayloadTooLargeError):
        use_case.execute(
            project_id=uuid4(),
            collection_id=uuid4(),
            filename='image.jpg',
            content_type='image/jpeg',
            file_stream=BytesIO(b'0123456789'),
            size_bytes=10,
            name='Image',
            description='',
            metadata=None,
        )


def test_upload_collection_item_deletes_object_when_db_create_fails() -> None:
    repository = FakeCollectionItemRepository(fail_on_create=True)
    object_storage = FakeObjectStorage()
    thumbnail_generator = FakeVideoThumbnailGenerator()
    use_case = UploadCollectionItemUseCase(
        repository,
        object_storage,
        thumbnail_generator,
        max_upload_size_bytes=1024,
        allowed_mime_prefixes=('image/', 'video/'),
    )

    with pytest.raises(RuntimeError):
        use_case.execute(
            project_id=uuid4(),
            collection_id=uuid4(),
            filename='clip.mp4',
            content_type='video/mp4',
            file_stream=BytesIO(b'video'),
            size_bytes=5,
            name='Clip',
            description='',
            metadata=None,
        )

    assert len(object_storage.uploaded) == 2
    assert set(object_storage.deleted_keys) == {stored.key for stored in object_storage.uploaded}
