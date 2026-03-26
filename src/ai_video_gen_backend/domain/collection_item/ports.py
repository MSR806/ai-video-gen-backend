from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ai_video_gen_backend.domain.types import JsonValue

from .entities import (
    CollectionItem,
    CollectionItemCreationPayload,
)


class CollectionItemRepositoryPort(Protocol):
    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]: ...

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None: ...

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem: ...

    def delete_item(self, item_id: UUID) -> bool: ...

    def get_items_by_run_id(self, run_id: UUID) -> list[CollectionItem]: ...

    def get_item_by_generation_run_output_id(
        self, generation_run_output_id: UUID
    ) -> CollectionItem | None: ...

    def mark_generated_item_ready(
        self,
        *,
        item_id: UUID,
        url: str,
        metadata: dict[str, JsonValue],
        storage_provider: str | None,
        storage_bucket: str | None,
        storage_key: str | None,
        mime_type: str | None,
        size_bytes: int | None,
    ) -> CollectionItem | None: ...

    def mark_generated_item_failed(
        self, *, item_id: UUID, error_message: str
    ) -> CollectionItem | None: ...

    def set_item_favorite(self, *, item_id: UUID, is_favorite: bool) -> CollectionItem | None: ...
