from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import (
    CollectionItem,
    CollectionItemCreationPayload,
    CollectionItemGenerationParams,
    GeneratedCollectionItem,
)


class CollectionItemRepositoryPort(Protocol):
    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]: ...

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None: ...

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem: ...

    def delete_item(self, item_id: UUID) -> bool: ...

    def generate_item(self, params: CollectionItemGenerationParams) -> GeneratedCollectionItem: ...
