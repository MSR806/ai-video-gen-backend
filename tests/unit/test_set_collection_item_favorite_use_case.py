from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ai_video_gen_backend.application.collection_item import SetCollectionItemFavoriteUseCase
from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    CollectionItemCreationPayload,
    JsonValue,
)


class FakeCollectionItemRepository:
    def __init__(self, items: list[CollectionItem]) -> None:
        self._items = {item.id: item for item in items}
        self.favorite_calls: list[tuple[UUID, bool]] = []

    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]:
        return [item for item in self._items.values() if item.collection_id == collection_id]

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None:
        return self._items.get(item_id)

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem:
        del payload
        raise NotImplementedError

    def delete_item(self, item_id: UUID) -> bool:
        del item_id
        raise NotImplementedError

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

    def set_item_favorite(self, *, item_id: UUID, is_favorite: bool) -> CollectionItem | None:
        self.favorite_calls.append((item_id, is_favorite))
        current = self._items.get(item_id)
        if current is None:
            return None

        updated = CollectionItem(
            id=current.id,
            project_id=current.project_id,
            collection_id=current.collection_id,
            media_type=current.media_type,
            status=current.status,
            name=current.name,
            description=current.description,
            url=current.url,
            metadata=current.metadata,
            generation_source=current.generation_source,
            generation_error_message=current.generation_error_message,
            created_at=current.created_at,
            updated_at=current.updated_at,
            run_id=current.run_id,
            generation_run_output_id=current.generation_run_output_id,
            storage_provider=current.storage_provider,
            storage_bucket=current.storage_bucket,
            storage_key=current.storage_key,
            mime_type=current.mime_type,
            size_bytes=current.size_bytes,
            is_favorite=is_favorite,
        )
        self._items[item_id] = updated
        return updated


def _item_fixture(*, collection_id: UUID) -> CollectionItem:
    now = datetime.now(UTC)
    return CollectionItem(
        id=uuid4(),
        project_id=uuid4(),
        collection_id=collection_id,
        media_type='image',
        status='READY',
        name='Item',
        description='Fixture',
        url='https://example.com/image.jpg',
        metadata={'thumbnailUrl': 'https://example.com/thumb.jpg'},
        generation_source='upload',
        generation_error_message=None,
        created_at=now,
        updated_at=now,
        is_favorite=False,
    )


def test_set_collection_item_favorite_updates_item() -> None:
    collection_id = uuid4()
    item = _item_fixture(collection_id=collection_id)
    repository = FakeCollectionItemRepository([item])
    use_case = SetCollectionItemFavoriteUseCase(repository)

    updated = use_case.execute(collection_id=collection_id, item_id=item.id, is_favorite=True)

    assert updated is not None
    assert updated.is_favorite is True
    assert repository.favorite_calls == [(item.id, True)]


def test_set_collection_item_favorite_returns_none_for_mismatched_collection() -> None:
    item = _item_fixture(collection_id=uuid4())
    repository = FakeCollectionItemRepository([item])
    use_case = SetCollectionItemFavoriteUseCase(repository)

    updated = use_case.execute(collection_id=uuid4(), item_id=item.id, is_favorite=True)

    assert updated is None
    assert repository.favorite_calls == []
