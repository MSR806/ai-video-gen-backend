from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ai_video_gen_backend.application.shot import EnsureShotVisualCollectionUseCase
from ai_video_gen_backend.domain.collection import Collection, CollectionCreationPayload
from ai_video_gen_backend.domain.screenplay import Screenplay, ScreenplayScene
from ai_video_gen_backend.domain.shot import Shot, ShotCreateInput, ShotUpdateInput


class FakeShotRepository:
    def __init__(self, shots: list[Shot]) -> None:
        self._shots = shots

    def list_shots(self, scene_id: UUID) -> list[Shot]:
        return [shot for shot in self._shots if shot.scene_id == scene_id]

    def get_shot(self, scene_id: UUID, shot_id: UUID) -> Shot | None:
        return next(
            (shot for shot in self._shots if shot.scene_id == scene_id and shot.id == shot_id),
            None,
        )

    def get_shot_by_collection_id(self, collection_id: UUID) -> Shot | None:
        return next((shot for shot in self._shots if shot.collection_id == collection_id), None)

    def create_shot(self, scene_id: UUID, payload: ShotCreateInput) -> Shot | None:
        del scene_id, payload
        raise NotImplementedError

    def update_shot(self, scene_id: UUID, shot_id: UUID, payload: ShotUpdateInput) -> Shot | None:
        del scene_id, shot_id, payload
        raise NotImplementedError

    def set_shot_collection(
        self, scene_id: UUID, shot_id: UUID, collection_id: UUID
    ) -> Shot | None:
        for index, shot in enumerate(self._shots):
            if shot.scene_id != scene_id or shot.id != shot_id:
                continue
            if shot.collection_id is not None:
                return shot
            linked = Shot(
                id=shot.id,
                scene_id=shot.scene_id,
                collection_id=collection_id,
                order_index=shot.order_index,
                title=shot.title,
                description=shot.description,
                camera_framing=shot.camera_framing,
                camera_movement=shot.camera_movement,
                mood=shot.mood,
                created_at=shot.created_at,
                updated_at=shot.updated_at,
            )
            self._shots[index] = linked
            return linked
        return None

    def delete_shot(self, scene_id: UUID, shot_id: UUID) -> bool:
        del scene_id, shot_id
        raise NotImplementedError

    def reorder_shots(self, scene_id: UUID, shot_ids: list[UUID]) -> list[Shot] | None:
        del scene_id, shot_ids
        raise NotImplementedError

    def replace_shots(self, scene_id: UUID, payloads: list[ShotCreateInput]) -> list[Shot] | None:
        del scene_id, payloads
        raise NotImplementedError


class FakeScreenplayRepository:
    def __init__(self, screenplay: Screenplay | None) -> None:
        self._screenplay = screenplay

    def get_screenplay_by_project_id(self, project_id: UUID) -> Screenplay | None:
        if self._screenplay is None or self._screenplay.project_id != project_id:
            return None
        return self._screenplay

    def create_screenplay(self, project_id: UUID, payload: object) -> Screenplay:
        del project_id, payload
        raise NotImplementedError

    def update_screenplay_title(self, screenplay_id: UUID, title: str) -> Screenplay | None:
        del screenplay_id, title
        raise NotImplementedError

    def create_screenplay_scene(self, screenplay_id: UUID, payload: object) -> Screenplay | None:
        del screenplay_id, payload
        raise NotImplementedError

    def update_screenplay_scene(
        self, screenplay_id: UUID, scene_id: UUID, payload: object
    ) -> ScreenplayScene | None:
        del screenplay_id, scene_id, payload
        raise NotImplementedError

    def delete_screenplay_scene(self, screenplay_id: UUID, scene_id: UUID) -> Screenplay | None:
        del screenplay_id, scene_id
        raise NotImplementedError

    def reorder_screenplay_scenes(
        self, screenplay_id: UUID, scene_ids: list[UUID]
    ) -> Screenplay | None:
        del screenplay_id, scene_ids
        raise NotImplementedError


class FakeCollectionRepository:
    def __init__(self, collections: list[Collection]) -> None:
        self.collections = collections
        self.create_calls = 0

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
        self.create_calls += 1
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


def _shot_fixture(
    *, scene_id: UUID, order_index: int, title: str, collection_id: UUID | None
) -> Shot:
    now = datetime.now(UTC)
    return Shot(
        id=uuid4(),
        scene_id=scene_id,
        collection_id=collection_id,
        order_index=order_index,
        title=title,
        description='',
        camera_framing='Wide',
        camera_movement='Static',
        mood='Neutral',
        created_at=now,
        updated_at=now,
    )


def _screenplay_fixture(project_id: UUID, scene_id: UUID) -> Screenplay:
    now = datetime.now(UTC)
    return Screenplay(
        id=uuid4(),
        project_id=project_id,
        title='Detective Story',
        scenes=[
            ScreenplayScene(
                id=scene_id,
                screenplay_id=uuid4(),
                order_index=1,
                content="<scene><action>INT. DETECTIVE'S OFFICE - NIGHT</action></scene>",
                shot_count=2,
                created_at=now,
                updated_at=now,
            )
        ],
        created_at=now,
        updated_at=now,
    )


def _screenplay_with_scene_fixtures(project_id: UUID, scene_ids: list[UUID]) -> Screenplay:
    now = datetime.now(UTC)
    scenes = [
        ScreenplayScene(
            id=scene_id,
            screenplay_id=uuid4(),
            order_index=index,
            content="<scene><action>INT. DETECTIVE'S OFFICE - NIGHT</action></scene>",
            shot_count=2,
            created_at=now,
            updated_at=now,
        )
        for index, scene_id in enumerate(scene_ids, start=1)
    ]
    return Screenplay(
        id=uuid4(),
        project_id=project_id,
        title='Detective Story',
        scenes=scenes,
        created_at=now,
        updated_at=now,
    )


def test_ensure_shot_visual_collection_creates_scene_and_shot_collection() -> None:
    project_id = uuid4()
    scene_id = uuid4()
    shot = _shot_fixture(
        scene_id=scene_id,
        order_index=1,
        title="Close-up of detective's hands",
        collection_id=None,
    )
    shot_repo = FakeShotRepository([shot])
    screenplay_repo = FakeScreenplayRepository(_screenplay_fixture(project_id, scene_id))
    collection_repo = FakeCollectionRepository([])

    created = EnsureShotVisualCollectionUseCase(
        shot_repository=shot_repo,
        screenplay_repository=screenplay_repo,
        collection_repository=collection_repo,
    ).execute(project_id=project_id, scene_id=scene_id, shot_id=shot.id)

    assert created is not None
    assert created.parent_collection_id is not None
    assert created.name == "Shot 1: Close-up of detective's hands"
    parent = collection_repo.get_collection_by_id(created.parent_collection_id)
    assert parent is not None
    assert parent.name == "Scene: INT. DETECTIVE'S OFFICE - NIGHT"
    linked_shot = shot_repo.get_shot(scene_id, shot.id)
    assert linked_shot is not None
    assert linked_shot.collection_id == created.id


def test_ensure_shot_visual_collection_reuses_existing_shot_collection() -> None:
    project_id = uuid4()
    scene_id = uuid4()
    now = datetime.now(UTC)
    existing = Collection(
        id=uuid4(),
        project_id=project_id,
        parent_collection_id=uuid4(),
        name='Shot 1: Existing',
        tag='shot',
        description='',
        created_at=now,
        updated_at=now,
    )
    shot = _shot_fixture(
        scene_id=scene_id, order_index=1, title='Existing', collection_id=existing.id
    )
    shot_repo = FakeShotRepository([shot])
    screenplay_repo = FakeScreenplayRepository(_screenplay_fixture(project_id, scene_id))
    collection_repo = FakeCollectionRepository([existing])

    resolved = EnsureShotVisualCollectionUseCase(
        shot_repository=shot_repo,
        screenplay_repository=screenplay_repo,
        collection_repository=collection_repo,
    ).execute(project_id=project_id, scene_id=scene_id, shot_id=shot.id)

    assert resolved == existing
    assert collection_repo.create_calls == 0


def test_ensure_shot_visual_collection_reuses_scene_parent_across_scene_shots() -> None:
    project_id = uuid4()
    scene_id = uuid4()
    now = datetime.now(UTC)
    parent = Collection(
        id=uuid4(),
        project_id=project_id,
        parent_collection_id=None,
        name="Scene: INT. DETECTIVE'S OFFICE - NIGHT",
        tag='scene',
        description=f'Auto-created scene visual collection [auto_scene_parent] scene_id={scene_id}',
        created_at=now,
        updated_at=now,
    )
    first_child = Collection(
        id=uuid4(),
        project_id=project_id,
        parent_collection_id=parent.id,
        name='Shot 1: Existing',
        tag='shot',
        description='',
        created_at=now,
        updated_at=now,
    )
    shot_one = _shot_fixture(
        scene_id=scene_id, order_index=1, title='Existing', collection_id=first_child.id
    )
    shot_two = _shot_fixture(
        scene_id=scene_id, order_index=2, title='Wide establishing shot', collection_id=None
    )
    shot_repo = FakeShotRepository([shot_one, shot_two])
    screenplay_repo = FakeScreenplayRepository(_screenplay_fixture(project_id, scene_id))
    collection_repo = FakeCollectionRepository([parent, first_child])

    created = EnsureShotVisualCollectionUseCase(
        shot_repository=shot_repo,
        screenplay_repository=screenplay_repo,
        collection_repository=collection_repo,
    ).execute(project_id=project_id, scene_id=scene_id, shot_id=shot_two.id)

    assert created is not None
    assert created.parent_collection_id == parent.id
    assert created.name == 'Shot 2: Wide establishing shot'
    assert collection_repo.create_calls == 1


def test_ensure_shot_visual_collection_ignores_non_matching_parent_from_linked_shot() -> None:
    project_id = uuid4()
    scene_id = uuid4()
    now = datetime.now(UTC)
    mismatched_parent = Collection(
        id=uuid4(),
        project_id=project_id,
        parent_collection_id=None,
        name='Scene: Different heading',
        tag='scene',
        description='',
        created_at=now,
        updated_at=now,
    )
    linked_child = Collection(
        id=uuid4(),
        project_id=project_id,
        parent_collection_id=mismatched_parent.id,
        name='Shot 1: Existing',
        tag='shot',
        description='',
        created_at=now,
        updated_at=now,
    )
    shot_one = _shot_fixture(
        scene_id=scene_id, order_index=1, title='Existing', collection_id=linked_child.id
    )
    shot_two = _shot_fixture(scene_id=scene_id, order_index=2, title='New shot', collection_id=None)
    shot_repo = FakeShotRepository([shot_one, shot_two])
    screenplay_repo = FakeScreenplayRepository(_screenplay_fixture(project_id, scene_id))
    collection_repo = FakeCollectionRepository([mismatched_parent, linked_child])

    created = EnsureShotVisualCollectionUseCase(
        shot_repository=shot_repo,
        screenplay_repository=screenplay_repo,
        collection_repository=collection_repo,
    ).execute(project_id=project_id, scene_id=scene_id, shot_id=shot_two.id)

    assert created is not None
    assert created.parent_collection_id is not None
    assert created.parent_collection_id != mismatched_parent.id
    parent = collection_repo.get_collection_by_id(created.parent_collection_id)
    assert parent is not None
    assert parent.tag == 'scene'
    assert parent.name == "Scene: INT. DETECTIVE'S OFFICE - NIGHT"


def test_ensure_shot_visual_collection_returns_none_when_project_screenplay_missing() -> None:
    project_id = uuid4()
    scene_id = uuid4()
    shot = _shot_fixture(scene_id=scene_id, order_index=1, title='Shot', collection_id=None)
    shot_repo = FakeShotRepository([shot])
    screenplay_repo = FakeScreenplayRepository(None)
    collection_repo = FakeCollectionRepository([])

    resolved = EnsureShotVisualCollectionUseCase(
        shot_repository=shot_repo,
        screenplay_repository=screenplay_repo,
        collection_repository=collection_repo,
    ).execute(project_id=project_id, scene_id=scene_id, shot_id=shot.id)

    assert resolved is None
    assert collection_repo.create_calls == 0


def test_ensure_shot_visual_collection_returns_none_when_scene_missing() -> None:
    project_id = uuid4()
    screenplay_scene_id = uuid4()
    requested_scene_id = uuid4()
    shot = _shot_fixture(
        scene_id=requested_scene_id, order_index=1, title='Shot', collection_id=None
    )
    shot_repo = FakeShotRepository([shot])
    screenplay_repo = FakeScreenplayRepository(_screenplay_fixture(project_id, screenplay_scene_id))
    collection_repo = FakeCollectionRepository([])

    resolved = EnsureShotVisualCollectionUseCase(
        shot_repository=shot_repo,
        screenplay_repository=screenplay_repo,
        collection_repository=collection_repo,
    ).execute(project_id=project_id, scene_id=requested_scene_id, shot_id=shot.id)

    assert resolved is None
    assert collection_repo.create_calls == 0


def test_ensure_shot_visual_collection_returns_none_when_shot_missing() -> None:
    project_id = uuid4()
    scene_id = uuid4()
    screenplay_repo = FakeScreenplayRepository(_screenplay_fixture(project_id, scene_id))
    collection_repo = FakeCollectionRepository([])

    resolved = EnsureShotVisualCollectionUseCase(
        shot_repository=FakeShotRepository([]),
        screenplay_repository=screenplay_repo,
        collection_repository=collection_repo,
    ).execute(project_id=project_id, scene_id=scene_id, shot_id=uuid4())

    assert resolved is None
    assert collection_repo.create_calls == 0


def test_ensure_shot_visual_collection_reuses_unlinked_matching_child_collection() -> None:
    project_id = uuid4()
    scene_id = uuid4()
    now = datetime.now(UTC)
    scene_parent = Collection(
        id=uuid4(),
        project_id=project_id,
        parent_collection_id=None,
        name="Scene: INT. DETECTIVE'S OFFICE - NIGHT",
        tag='scene',
        description=f'Auto-created scene visual collection [auto_scene_parent] scene_id={scene_id}',
        created_at=now,
        updated_at=now,
    )
    existing_child = Collection(
        id=uuid4(),
        project_id=project_id,
        parent_collection_id=scene_parent.id,
        name='Shot 2: Wide establishing shot',
        tag='shot',
        description='',
        created_at=now,
        updated_at=now,
    )
    shot_one = _shot_fixture(
        scene_id=scene_id,
        order_index=1,
        title='Existing',
        collection_id=uuid4(),
    )
    shot_two = _shot_fixture(
        scene_id=scene_id,
        order_index=2,
        title='Wide establishing shot',
        collection_id=None,
    )
    shot_repo = FakeShotRepository([shot_one, shot_two])
    screenplay_repo = FakeScreenplayRepository(_screenplay_fixture(project_id, scene_id))
    collection_repo = FakeCollectionRepository([scene_parent, existing_child])

    resolved = EnsureShotVisualCollectionUseCase(
        shot_repository=shot_repo,
        screenplay_repository=screenplay_repo,
        collection_repository=collection_repo,
    ).execute(project_id=project_id, scene_id=scene_id, shot_id=shot_two.id)

    assert resolved == existing_child
    assert collection_repo.create_calls == 0
    linked_shot = shot_repo.get_shot(scene_id, shot_two.id)
    assert linked_shot is not None
    assert linked_shot.collection_id == existing_child.id


def test_ensure_shot_visual_collection_keeps_scene_collection_isolated() -> None:
    project_id = uuid4()
    first_scene_id = uuid4()
    second_scene_id = uuid4()
    first_shot = _shot_fixture(
        scene_id=first_scene_id,
        order_index=1,
        title='Match Cut',
        collection_id=None,
    )
    second_shot = _shot_fixture(
        scene_id=second_scene_id,
        order_index=1,
        title='Match Cut',
        collection_id=None,
    )
    shot_repo = FakeShotRepository([first_shot, second_shot])
    screenplay_repo = FakeScreenplayRepository(
        _screenplay_with_scene_fixtures(project_id, [first_scene_id, second_scene_id])
    )
    collection_repo = FakeCollectionRepository([])
    use_case = EnsureShotVisualCollectionUseCase(
        shot_repository=shot_repo,
        screenplay_repository=screenplay_repo,
        collection_repository=collection_repo,
    )

    first_collection = use_case.execute(
        project_id=project_id,
        scene_id=first_scene_id,
        shot_id=first_shot.id,
    )
    second_collection = use_case.execute(
        project_id=project_id,
        scene_id=second_scene_id,
        shot_id=second_shot.id,
    )

    assert first_collection is not None
    assert second_collection is not None
    assert first_collection.id != second_collection.id
    assert first_collection.parent_collection_id is not None
    assert second_collection.parent_collection_id is not None
    assert first_collection.parent_collection_id != second_collection.parent_collection_id

    first_parent = collection_repo.get_collection_by_id(first_collection.parent_collection_id)
    second_parent = collection_repo.get_collection_by_id(second_collection.parent_collection_id)
    assert first_parent is not None
    assert second_parent is not None
    assert first_parent.name == second_parent.name
    assert first_parent.description != second_parent.description
