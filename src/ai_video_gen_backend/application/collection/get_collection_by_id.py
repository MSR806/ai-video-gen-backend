from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.collection import Collection, CollectionRepositoryPort


class GetCollectionByIdUseCase:
    def __init__(self, collection_repository: CollectionRepositoryPort) -> None:
        self._collection_repository = collection_repository

    def execute(self, collection_id: UUID) -> Collection | None:
        return self._collection_repository.get_collection_by_id(collection_id)
