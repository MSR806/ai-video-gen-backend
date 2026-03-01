from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.collection_item import CollectionItem, CollectionItemRepositoryPort


class GetCollectionItemsUseCase:
    def __init__(self, collection_item_repository: CollectionItemRepositoryPort) -> None:
        self._collection_item_repository = collection_item_repository

    def execute(self, collection_id: UUID) -> list[CollectionItem]:
        return self._collection_item_repository.get_items_by_collection_id(collection_id)
