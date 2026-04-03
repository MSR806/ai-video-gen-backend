from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.collection import Collection
from ai_video_gen_backend.domain.collection_item import CollectionItem
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema
from ai_video_gen_backend.presentation.api.v1.schemas.collection_item_schema import (
    CollectionItemReadResponse,
)


class CollectionResponse(StrictSchema):
    id: UUID
    project_id: UUID = Field(alias='projectId')
    parent_collection_id: UUID | None = Field(default=None, alias='parentCollectionId')
    name: str
    tag: str
    description: str
    thumbnail_url: str | None = Field(default=None, alias='thumbnailUrl')
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')

    @classmethod
    def from_domain(
        cls,
        collection: Collection,
        *,
        thumbnail_url: str | None = None,
    ) -> CollectionResponse:
        return cls(
            id=collection.id,
            project_id=collection.project_id,
            parent_collection_id=collection.parent_collection_id,
            name=collection.name,
            tag=collection.tag,
            description=collection.description,
            thumbnail_url=thumbnail_url,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )


def resolve_collection_thumbnail_url(items: list[CollectionItem]) -> str | None:
    if not items:
        return None

    thumbnail_url = items[0].metadata.get('thumbnailUrl')
    if isinstance(thumbnail_url, str) and thumbnail_url.strip() != '':
        return thumbnail_url
    return None


class CollectionContentsResponse(StrictSchema):
    items: list[CollectionItemReadResponse]
    child_collections: list[CollectionResponse] = Field(alias='childCollections')


class CreateCollectionRequest(StrictSchema):
    name: str
    tag: str
    description: str
    parent_collection_id: UUID | None = Field(default=None, alias='parentCollectionId')
