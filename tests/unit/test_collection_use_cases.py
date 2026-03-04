from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ai_video_gen_backend.application.collection import (
    CreateCollectionUseCase,
    GetCollectionByIdUseCase,
    GetProjectCollectionsUseCase,
)
from ai_video_gen_backend.domain.collection import Collection, CollectionCreationPayload


class FakeCollectionRepository:
    def __init__(self, collections: list[Collection]) -> None:
        self.collections = collections

    def get_collections_by_project_id(self, project_id: UUID) -> list[Collection]:
        return [
            collection for collection in self.collections if collection.project_id == project_id
        ]

    def get_child_collections(self, parent_collection_id: UUID) -> list[Collection]:
        return [
            collection
            for collection in self.collections
            if collection.parent_collection_id == parent_collection_id
        ]

    def get_collection_by_id(self, collection_id: UUID) -> Collection | None:
        return next(
            (collection for collection in self.collections if collection.id == collection_id),
            None,
        )

    def create_collection(self, payload: CollectionCreationPayload) -> Collection:
        now = datetime.now(UTC)
        collection = Collection(
            id=uuid4(),
            project_id=payload.project_id,
            parent_collection_id=payload.parent_collection_id,
            name=payload.name,
            tag=payload.tag,
            description=payload.description,
            created_at=now,
            updated_at=now,
        )
        self.collections.append(collection)
        return collection


def _collection_fixture(collection_id: UUID, project_id: UUID, name: str) -> Collection:
    now = datetime.now(UTC)
    return Collection(
        id=collection_id,
        project_id=project_id,
        parent_collection_id=None,
        name=name,
        tag='reference',
        description='Fixture collection',
        created_at=now,
        updated_at=now,
    )


def test_get_project_collections_use_case_filters_by_project() -> None:
    project_a = uuid4()
    project_b = uuid4()

    repo = FakeCollectionRepository(
        [
            _collection_fixture(uuid4(), project_a, 'A1'),
            _collection_fixture(uuid4(), project_a, 'A2'),
            _collection_fixture(uuid4(), project_b, 'B1'),
        ]
    )

    use_case = GetProjectCollectionsUseCase(repo)
    result = use_case.execute(project_a)

    assert len(result) == 2
    assert all(collection.project_id == project_a for collection in result)


def test_get_collection_by_id_use_case_returns_none_when_missing() -> None:
    project_id = uuid4()
    repo = FakeCollectionRepository([_collection_fixture(uuid4(), project_id, 'Only')])

    use_case = GetCollectionByIdUseCase(repo)
    result = use_case.execute(uuid4())

    assert result is None


def test_create_collection_use_case_creates_collection() -> None:
    project_id = uuid4()
    repo = FakeCollectionRepository([])
    use_case = CreateCollectionUseCase(repo)

    result = use_case.execute(
        CollectionCreationPayload(
            project_id=project_id,
            name='New Collection',
            tag='characters',
            description='Contains character references',
            parent_collection_id=None,
        )
    )

    assert result.name == 'New Collection'
    assert result.tag == 'characters'
    assert result.project_id == project_id
    assert result.parent_collection_id is None
    assert len(repo.collections) == 1
