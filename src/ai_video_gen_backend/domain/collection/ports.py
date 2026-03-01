from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import Collection, CollectionCreationPayload


class CollectionRepositoryPort(Protocol):
    def get_collections_by_project_id(self, project_id: UUID) -> list[Collection]: ...

    def get_collection_by_id(self, collection_id: UUID) -> Collection | None: ...

    def create_collection(self, payload: CollectionCreationPayload) -> Collection: ...
