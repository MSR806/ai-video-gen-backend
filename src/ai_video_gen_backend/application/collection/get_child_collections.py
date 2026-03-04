from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.collection import Collection, CollectionRepositoryPort


class GetChildCollectionsUseCase:
    def __init__(self, collection_repository: CollectionRepositoryPort) -> None:
        self._collection_repository = collection_repository

    def execute(self, parent_collection_id: UUID) -> list[Collection]:
        return self._collection_repository.get_child_collections(parent_collection_id)
