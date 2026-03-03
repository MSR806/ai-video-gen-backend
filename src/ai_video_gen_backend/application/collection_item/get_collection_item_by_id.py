from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.collection_item import CollectionItem, CollectionItemRepositoryPort


class GetCollectionItemByIdUseCase:
    def __init__(self, collection_item_repository: CollectionItemRepositoryPort) -> None:
        self._collection_item_repository = collection_item_repository

    def execute(self, item_id: UUID) -> CollectionItem | None:
        return self._collection_item_repository.get_item_by_id(item_id)
