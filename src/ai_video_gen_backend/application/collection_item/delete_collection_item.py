from __future__ import annotations

from pathlib import Path
from uuid import UUID

from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    CollectionItemRepositoryPort,
    ObjectStoragePort,
)


class DeleteCollectionItemUseCase:
    def __init__(
        self,
        collection_item_repository: CollectionItemRepositoryPort,
        object_storage: ObjectStoragePort,
    ) -> None:
        self._collection_item_repository = collection_item_repository
        self._object_storage = object_storage

    def execute(self, *, collection_id: UUID, item_id: UUID) -> bool:
        item = self._collection_item_repository.get_item_by_id(item_id)
        if item is None or item.collection_id != collection_id:
            return False

        for key in self._storage_keys(item):
            self._object_storage.delete_object(key=key)

        return self._collection_item_repository.delete_item(item_id)

    def _storage_keys(self, item: CollectionItem) -> list[str]:
        if item.storage_key is None:
            return []

        keys = [item.storage_key]
        if item.media_type == 'video':
            keys.append(self._thumbnail_storage_key(item.storage_key))

        return list(dict.fromkeys(keys))

    def _thumbnail_storage_key(self, object_key: str) -> str:
        object_path = Path(object_key)
        if len(object_path.suffix) > 0:
            return f'{object_key[: -len(object_path.suffix)]}-thumb.jpg'
        return f'{object_key}-thumb.jpg'
