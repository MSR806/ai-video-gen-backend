from __future__ import annotations

from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    CollectionItemCreationPayload,
    CollectionItemRepositoryPort,
)


class CreateCollectionItemUseCase:
    def __init__(self, collection_item_repository: CollectionItemRepositoryPort) -> None:
        self._collection_item_repository = collection_item_repository

    def execute(self, payload: CollectionItemCreationPayload) -> CollectionItem:
        return self._collection_item_repository.create_item(payload)
