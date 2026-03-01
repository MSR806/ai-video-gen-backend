from __future__ import annotations

from ai_video_gen_backend.domain.collection import (
    Collection,
    CollectionCreationPayload,
    CollectionRepositoryPort,
)


class CreateCollectionUseCase:
    def __init__(self, collection_repository: CollectionRepositoryPort) -> None:
        self._collection_repository = collection_repository

    def execute(self, payload: CollectionCreationPayload) -> Collection:
        return self._collection_repository.create_collection(payload)
