from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.collection_item import CollectionItem, CollectionItemRepositoryPort


class SetCollectionItemFavoriteUseCase:
    def __init__(self, collection_item_repository: CollectionItemRepositoryPort) -> None:
        self._collection_item_repository = collection_item_repository

    def execute(
        self,
        *,
        collection_id: UUID,
        item_id: UUID,
        is_favorite: bool,
    ) -> CollectionItem | None:
        item = self._collection_item_repository.get_item_by_id(item_id)
        if item is None or item.collection_id != collection_id:
            return None

        return self._collection_item_repository.set_item_favorite(
            item_id=item_id,
            is_favorite=is_favorite,
        )
