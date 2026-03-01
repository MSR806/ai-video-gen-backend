from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.collection import Collection
from ai_video_gen_backend.infrastructure.db.models import CollectionModel


class CollectionSqlRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_collections_by_project_id(self, project_id: UUID) -> list[Collection]:
        stmt = (
            select(CollectionModel)
            .where(CollectionModel.project_id == project_id)
            .order_by(CollectionModel.created_at.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(record) for record in records]

    def get_collection_by_id(self, collection_id: UUID) -> Collection | None:
        stmt = select(CollectionModel).where(CollectionModel.id == collection_id)
        record = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(record) if record is not None else None

    def _to_domain(self, model: CollectionModel) -> Collection:
        return Collection(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            tag=model.tag,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
