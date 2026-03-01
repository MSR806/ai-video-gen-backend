from __future__ import annotations

from ai_video_gen_backend.domain.collection_item import (
    CollectionItemGenerationParams,
    CollectionItemRepositoryPort,
    GeneratedCollectionItem,
)


class GenerateCollectionItemUseCase:
    def __init__(self, collection_item_repository: CollectionItemRepositoryPort) -> None:
        self._collection_item_repository = collection_item_repository

    def execute(self, params: CollectionItemGenerationParams) -> GeneratedCollectionItem:
        return self._collection_item_repository.generate_item(params)
