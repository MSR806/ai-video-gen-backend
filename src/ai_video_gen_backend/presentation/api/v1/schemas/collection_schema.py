from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.collection import Collection
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class CollectionResponse(StrictSchema):
    id: UUID
    project_id: UUID = Field(alias='projectId')
    name: str
    tag: str
    description: str
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')

    @classmethod
    def from_domain(cls, collection: Collection) -> CollectionResponse:
        return cls(
            id=collection.id,
            project_id=collection.project_id,
            name=collection.name,
            tag=collection.tag,
            description=collection.description,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )


class CreateCollectionRequest(StrictSchema):
    name: str
    tag: str
    description: str
