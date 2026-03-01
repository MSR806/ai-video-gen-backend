from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.collection import Collection, CollectionRepositoryPort


class GetProjectCollectionsUseCase:
    def __init__(self, collection_repository: CollectionRepositoryPort) -> None:
        self._collection_repository = collection_repository

    def execute(self, project_id: UUID) -> list[Collection]:
        return self._collection_repository.get_collections_by_project_id(project_id)
