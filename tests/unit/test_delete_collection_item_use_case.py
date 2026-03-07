from __future__ import annotations

from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.collection_item import (
    DeleteCollectionItemUseCase,
    DeleteStorageFailureError,
)
from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    CollectionItemCreationPayload,
    CollectionItemGenerationParams,
    GeneratedCollectionItem,
    JsonValue,
    MediaType,
    StorageError,
    StoredObject,
)


class FakeCollectionItemRepository:
    def __init__(self, items: list[CollectionItem]) -> None:
        self._items = {item.id: item for item in items}
        self.deleted_ids: list[UUID] = []

    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]:
        return [item for item in self._items.values() if item.collection_id == collection_id]

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None:
        return self._items.get(item_id)

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem:
        del payload
        raise NotImplementedError

    def delete_item(self, item_id: UUID) -> bool:
        if item_id not in self._items:
            return False

        self.deleted_ids.append(item_id)
        del self._items[item_id]
        return True

    def get_items_by_run_id(self, run_id: UUID) -> list[CollectionItem]:
        del run_id
        return []

    def get_item_by_generation_run_output_id(
        self, generation_run_output_id: UUID
    ) -> CollectionItem | None:
        del generation_run_output_id
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
    def __init__(self, *, fail_on_keys: set[str] | None = None) -> None:
        self.deleted_keys: list[str] = []
        self._fail_on_keys = fail_on_keys or set()

    def upload_object(
        self,
        *,
        key: str,
        content_type: str,
        body: BinaryIO,
        size_bytes: int,
    ) -> StoredObject:
        del key, content_type, body, size_bytes
        raise NotImplementedError

    def delete_object(self, *, key: str) -> None:
        if key in self._fail_on_keys:
            raise StorageError('delete failed')
        self.deleted_keys.append(key)


def _item_fixture(
    *,
    collection_id: UUID,
    media_type: MediaType,
    storage_key: str | None,
) -> CollectionItem:
    now = datetime.now(UTC)
    return CollectionItem(
        id=uuid4(),
        project_id=uuid4(),
        collection_id=collection_id,
        media_type=media_type,
        status='READY',
        name='Item',
        description='desc',
        url='https://example.com/item',
        metadata={'thumbnailUrl': 'https://example.com/thumb.jpg'},
        generation_source='upload',
        generation_error_message=None,
        created_at=now,
        updated_at=now,
        storage_provider='s3' if storage_key is not None else None,
        storage_bucket='media' if storage_key is not None else None,
        storage_key=storage_key,
        mime_type='image/jpeg' if media_type == 'image' else 'video/mp4',
        size_bytes=123,
    )


def test_delete_collection_item_deletes_image_storage_object_and_row() -> None:
    collection_id = uuid4()
    item = _item_fixture(
        collection_id=collection_id,
        media_type='image',
        storage_key='projects/p/collections/c/image.jpg',
    )
    repository = FakeCollectionItemRepository([item])
    object_storage = FakeObjectStorage()
    use_case = DeleteCollectionItemUseCase(repository, object_storage)

    deleted = use_case.execute(collection_id=collection_id, item_id=item.id)

    assert deleted is True
    assert repository.deleted_ids == [item.id]
    assert object_storage.deleted_keys == ['projects/p/collections/c/image.jpg']


def test_delete_collection_item_deletes_video_thumbnail_object() -> None:
    collection_id = uuid4()
    item = _item_fixture(
        collection_id=collection_id,
        media_type='video',
        storage_key='projects/p/collections/c/clip.mp4',
    )
    repository = FakeCollectionItemRepository([item])
    object_storage = FakeObjectStorage()
    use_case = DeleteCollectionItemUseCase(repository, object_storage)

    deleted = use_case.execute(collection_id=collection_id, item_id=item.id)

    assert deleted is True
    assert object_storage.deleted_keys == [
        'projects/p/collections/c/clip.mp4',
        'projects/p/collections/c/clip-thumb.jpg',
    ]


def test_delete_collection_item_returns_false_when_item_is_missing() -> None:
    repository = FakeCollectionItemRepository([])
    object_storage = FakeObjectStorage()
    use_case = DeleteCollectionItemUseCase(repository, object_storage)

    deleted = use_case.execute(collection_id=uuid4(), item_id=uuid4())

    assert deleted is False
    assert repository.deleted_ids == []
    assert object_storage.deleted_keys == []


def test_delete_collection_item_returns_false_when_item_belongs_to_other_collection() -> None:
    item = _item_fixture(
        collection_id=uuid4(),
        media_type='image',
        storage_key='projects/p/collections/c/image.jpg',
    )
    repository = FakeCollectionItemRepository([item])
    object_storage = FakeObjectStorage()
    use_case = DeleteCollectionItemUseCase(repository, object_storage)

    deleted = use_case.execute(collection_id=uuid4(), item_id=item.id)

    assert deleted is False
    assert repository.deleted_ids == []
    assert object_storage.deleted_keys == []


def test_delete_collection_item_raises_when_storage_delete_fails() -> None:
    collection_id = uuid4()
    object_key = 'projects/p/collections/c/image.jpg'
    item = _item_fixture(
        collection_id=collection_id,
        media_type='image',
        storage_key=object_key,
    )
    repository = FakeCollectionItemRepository([item])
    object_storage = FakeObjectStorage(fail_on_keys={object_key})
    use_case = DeleteCollectionItemUseCase(repository, object_storage)

    with pytest.raises(DeleteStorageFailureError):
        use_case.execute(collection_id=collection_id, item_id=item.id)

    assert repository.deleted_ids == []
