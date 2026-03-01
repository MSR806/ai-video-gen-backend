from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.collection_item import (
    AspectRatio,
    CollectionItem,
    CollectionItemCreationPayload,
    CollectionItemGenerationParams,
    GeneratedCollectionItem,
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
            name=payload.name,
            description=payload.description,
            url=payload.url,
            metadata_json=payload.metadata,
            generation_source=payload.generation_source,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def generate_item(self, params: CollectionItemGenerationParams) -> GeneratedCollectionItem:
        resolution = params.resolution or '2k'
        width, height = self._dimensions(params.aspect_ratio, resolution)

        seed_source = (
            f'{params.prompt}|{params.media_type}|{params.aspect_ratio}'
            f'|{resolution}|{params.collection_id}'
        )
        seed = hashlib.sha256(seed_source.encode('utf-8')).hexdigest()[:16]

        extension = 'jpg' if params.media_type == 'image' else 'mp4'
        return GeneratedCollectionItem(
            url=f'https://generated.example/{seed}.{extension}',
            thumbnail_url=f'https://generated.example/{seed}-thumb.jpg',
            width=width,
            height=height,
            format=extension,
            duration=10 if params.media_type == 'video' else None,
        )

    def _dimensions(self, aspect_ratio: AspectRatio, resolution: str) -> tuple[int, int]:
        base_widths = {'2k': 2048, '4k': 4096, '8k': 8192}
        width = base_widths[resolution]

        if aspect_ratio == 'square':
            return width, width
        if aspect_ratio == 'portrait':
            return width, round(width * 1.5)
        return width, round(width / 1.9)

    def _to_domain(self, model: CollectionItemModel) -> CollectionItem:
        metadata: dict[str, JsonValue] = model.metadata_json
        return CollectionItem(
            id=model.id,
            project_id=model.project_id,
            collection_id=model.collection_id,
            media_type=model.media_type,
            name=model.name,
            description=model.description,
            url=model.url,
            metadata=metadata,
            generation_source=model.generation_source,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
