from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    CollectionItemCreationPayload,
    CollectionItemStatus,
    JsonValue,
)
from ai_video_gen_backend.infrastructure.db.models import CollectionItemModel


class CollectionItemSqlRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]:
        stmt = (
            select(CollectionItemModel)
            .where(CollectionItemModel.collection_id == collection_id)
            .order_by(CollectionItemModel.created_at.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(record) for record in records]

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None:
        stmt = select(CollectionItemModel).where(CollectionItemModel.id == item_id)
        record = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(record) if record is not None else None

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem:
        model = CollectionItemModel(
            project_id=payload.project_id,
            collection_id=payload.collection_id,
            media_type=payload.media_type,
            status=payload.status,
            name=payload.name,
            description=payload.description,
            url=payload.url,
            metadata_json=payload.metadata,
            generation_source=payload.generation_source,
            generation_error_message=payload.generation_error_message,
            storage_provider=payload.storage_provider,
            storage_bucket=payload.storage_bucket,
            storage_key=payload.storage_key,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def delete_item(self, item_id: UUID) -> bool:
        model = self._session.get(CollectionItemModel, item_id)
        if model is None:
            return False

        self._session.delete(model)
        self._session.commit()
        return True

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
    ) -> CollectionItem | None:
        model = self._session.get(CollectionItemModel, item_id)
        if model is None:
            return None

        model.status = 'READY'
        model.url = url
        model.metadata_json = metadata
        model.generation_error_message = None
        model.storage_provider = storage_provider
        model.storage_bucket = storage_bucket
        model.storage_key = storage_key
        model.mime_type = mime_type
        model.size_bytes = size_bytes
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def mark_generated_item_failed(
        self, *, item_id: UUID, error_message: str
    ) -> CollectionItem | None:
        model = self._session.get(CollectionItemModel, item_id)
        if model is None:
            return None

        model.status = 'FAILED'
        model.generation_error_message = error_message
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def _to_domain(self, model: CollectionItemModel) -> CollectionItem:
        metadata: dict[str, JsonValue] = model.metadata_json
        return CollectionItem(
            id=model.id,
            project_id=model.project_id,
            collection_id=model.collection_id,
            media_type=model.media_type,
            status=cast(CollectionItemStatus, model.status),
            name=model.name,
            description=model.description,
            url=model.url,
            metadata=metadata,
            generation_source=model.generation_source,
            generation_error_message=model.generation_error_message,
            storage_provider=model.storage_provider,
            storage_bucket=model.storage_bucket,
            storage_key=model.storage_key,
            mime_type=model.mime_type,
            size_bytes=model.size_bytes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
