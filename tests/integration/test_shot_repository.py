from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.shot import ShotCreateInput, ShotUpdateInput
from ai_video_gen_backend.infrastructure.db.models import (
    CollectionModel,
    ProjectModel,
    ScreenplayModel,
    ScreenplaySceneModel,
    ShotModel,
)
from ai_video_gen_backend.infrastructure.repositories import ShotSqlRepository


def _seed_scene(db_session: Session, label: str) -> tuple[UUID, UUID, UUID]:
    project_id = uuid4()
    screenplay_id = uuid4()
    scene_id = uuid4()

    db_session.add(
        ProjectModel(
            id=project_id,
            name=f'Project {label}',
            description='Project for shot repository test',
            status='draft',
        )
    )
    db_session.add(
        ScreenplayModel(
            id=screenplay_id,
            project_id=project_id,
            title=f'Screenplay {label}',
        )
    )
    db_session.add(
        ScreenplaySceneModel(
            id=scene_id,
            screenplay_id=screenplay_id,
            order_index=1,
            content_xml='<scene><action>Test</action></scene>',
        )
    )
    db_session.commit()

    return project_id, screenplay_id, scene_id


def test_shot_repository_crud_and_reorder_is_scene_scoped(db_session: Session) -> None:
    _, _, scene_a_uuid = _seed_scene(db_session, 'A')
    _, _, scene_b_uuid = _seed_scene(db_session, 'B')

    repository = ShotSqlRepository(db_session)

    first = repository.create_shot(
        scene_a_uuid,
        ShotCreateInput(
            title='Shot A1',
            description='First shot in scene A',
            camera_framing='Wide',
            camera_movement='Pan left',
            mood='Calm',
        ),
    )
    second = repository.create_shot(
        scene_a_uuid,
        ShotCreateInput(
            title='Shot A2',
            description='Second shot in scene A',
            camera_framing='Close-up',
            camera_movement='Static',
            mood='Tense',
        ),
    )
    third = repository.create_shot(
        scene_b_uuid,
        ShotCreateInput(
            title='Shot B1',
            description='Only shot in scene B',
            camera_framing='Medium',
            camera_movement='Dolly out',
            mood='Bright',
        ),
    )

    assert first is not None
    assert second is not None
    assert third is not None
    assert [shot.order_index for shot in repository.list_shots(scene_a_uuid)] == [1, 2]
    assert [shot.order_index for shot in repository.list_shots(scene_b_uuid)] == [1]
    assert first.collection_id is None
    assert second.collection_id is None

    updated = repository.update_shot(scene_a_uuid, first.id, ShotUpdateInput(mood='Ominous'))
    assert updated is not None
    assert updated.mood == 'Ominous'

    reordered = repository.reorder_shots(scene_a_uuid, [second.id, first.id])
    assert reordered is not None
    assert [shot.id for shot in reordered] == [second.id, first.id]
    assert [shot.order_index for shot in reordered] == [1, 2]
    assert [shot.order_index for shot in repository.list_shots(scene_b_uuid)] == [1]

    deleted = repository.delete_shot(scene_a_uuid, second.id)
    assert deleted is True
    assert [shot.order_index for shot in repository.list_shots(scene_a_uuid)] == [1]


def test_shot_repository_respects_scene_cascade_delete(db_session: Session) -> None:
    project_id = uuid4()
    screenplay_id = uuid4()
    scene_id = uuid4()

    db_session.add(
        ProjectModel(
            id=project_id,
            name='Project',
            description='Project for cascade test',
            status='draft',
        )
    )
    db_session.add(
        ScreenplayModel(
            id=screenplay_id,
            project_id=project_id,
            title='Screenplay',
        )
    )
    scene = ScreenplaySceneModel(
        id=scene_id,
        screenplay_id=screenplay_id,
        order_index=1,
        content_xml='<scene><action>Cascade</action></scene>',
    )
    db_session.add(scene)
    db_session.commit()

    repository = ShotSqlRepository(db_session)
    created = repository.create_shot(
        scene_id,
        ShotCreateInput(
            title='Shot to delete',
            description='Will be removed by cascade',
            camera_framing='Wide',
            camera_movement='Static',
            mood='Neutral',
        ),
    )
    assert created is not None

    db_session.delete(scene)
    db_session.commit()

    stmt = select(ShotModel).where(ShotModel.id == created.id)
    assert db_session.execute(stmt).scalar_one_or_none() is None


def test_replace_shots_rolls_back_when_delete_phase_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, scene_id = _seed_scene(db_session, 'ReplaceRollback')
    repository = ShotSqlRepository(db_session)

    first = repository.create_shot(
        scene_id,
        ShotCreateInput(
            title='Existing 1',
            description='Keep on failure',
            camera_framing='Wide',
            camera_movement='Static',
            mood='Calm',
        ),
    )
    second = repository.create_shot(
        scene_id,
        ShotCreateInput(
            title='Existing 2',
            description='Keep on failure',
            camera_framing='Close-up',
            camera_movement='Pan left',
            mood='Tense',
        ),
    )
    assert first is not None
    assert second is not None

    def failing_flush() -> None:
        raise RuntimeError('simulated flush failure')

    monkeypatch.setattr(db_session, 'flush', failing_flush)

    with pytest.raises(RuntimeError, match='simulated flush failure'):
        repository.replace_shots(
            scene_id,
            [
                ShotCreateInput(
                    title='Generated 1',
                    description='New one',
                    camera_framing='Medium',
                    camera_movement='Dolly in',
                    mood='Excited',
                )
            ],
        )

    preserved = repository.list_shots(scene_id)
    assert [shot.title for shot in preserved] == ['Existing 1', 'Existing 2']
    assert [shot.order_index for shot in preserved] == [1, 2]


def test_shot_repository_maps_collection_id_when_present(db_session: Session) -> None:
    project_id, _, scene_id = _seed_scene(db_session, 'CollectionLink')
    collection_id = uuid4()
    db_session.add(
        CollectionModel(
            id=collection_id,
            project_id=project_id,
            name='Shot refs',
            tag='shots',
            description='Collection for shot references',
        )
    )

    shot_id = uuid4()
    db_session.add(
        ShotModel(
            id=shot_id,
            scene_id=scene_id,
            collection_id=collection_id,
            order_index=1,
            title='Linked shot',
            description='Has collection link',
            camera_framing='Wide',
            camera_movement='Static',
            mood='Calm',
        )
    )
    db_session.commit()

    shot = ShotSqlRepository(db_session).list_shots(scene_id)[0]
    assert shot.id == shot_id
    assert shot.collection_id == collection_id


def test_get_shot_is_scene_scoped(db_session: Session) -> None:
    _, _, scene_a_id = _seed_scene(db_session, 'GetShotA')
    _, _, scene_b_id = _seed_scene(db_session, 'GetShotB')
    repository = ShotSqlRepository(db_session)

    created = repository.create_shot(
        scene_a_id,
        ShotCreateInput(
            title='Scoped shot',
            description='Scene A only',
            camera_framing='Wide',
            camera_movement='Static',
            mood='Neutral',
        ),
    )
    assert created is not None

    assert repository.get_shot(scene_a_id, created.id) is not None
    assert repository.get_shot(scene_b_id, created.id) is None


def test_set_shot_collection_updates_only_with_matching_scene(db_session: Session) -> None:
    project_a_id, _, scene_a_id = _seed_scene(db_session, 'SetCollectionA')
    project_b_id, _, scene_b_id = _seed_scene(db_session, 'SetCollectionB')
    repository = ShotSqlRepository(db_session)

    created = repository.create_shot(
        scene_a_id,
        ShotCreateInput(
            title='Collection target',
            description='Collection assignment',
            camera_framing='Close-up',
            camera_movement='Pan left',
            mood='Tense',
        ),
    )
    assert created is not None

    collection_id = uuid4()
    db_session.add(
        CollectionModel(
            id=collection_id,
            project_id=project_a_id,
            name='Shot refs',
            tag='shot',
            description='Collection for shots',
        )
    )
    unrelated_collection_id = uuid4()
    db_session.add(
        CollectionModel(
            id=unrelated_collection_id,
            project_id=project_b_id,
            name='Other refs',
            tag='shot',
            description='Different project collection',
        )
    )
    db_session.commit()

    wrong_scene_update = repository.set_shot_collection(
        scene_b_id, created.id, unrelated_collection_id
    )
    assert wrong_scene_update is None
    unchanged = repository.get_shot(scene_a_id, created.id)
    assert unchanged is not None
    assert unchanged.collection_id is None

    updated = repository.set_shot_collection(scene_a_id, created.id, collection_id)
    assert updated is not None
    assert updated.collection_id == collection_id


def test_set_shot_collection_does_not_overwrite_existing_link(db_session: Session) -> None:
    project_id, _, scene_id = _seed_scene(db_session, 'SetCollectionLocked')
    repository = ShotSqlRepository(db_session)

    created = repository.create_shot(
        scene_id,
        ShotCreateInput(
            title='Collection lock target',
            description='Preserve initial link',
            camera_framing='Close-up',
            camera_movement='Static',
            mood='Calm',
        ),
    )
    assert created is not None

    initial_collection_id = uuid4()
    next_collection_id = uuid4()
    db_session.add(
        CollectionModel(
            id=initial_collection_id,
            project_id=project_id,
            name='Initial refs',
            tag='shot',
            description='Initial shot collection',
        )
    )
    db_session.add(
        CollectionModel(
            id=next_collection_id,
            project_id=project_id,
            name='Next refs',
            tag='shot',
            description='Secondary shot collection',
        )
    )
    db_session.commit()

    first_link = repository.set_shot_collection(scene_id, created.id, initial_collection_id)
    assert first_link is not None
    assert first_link.collection_id == initial_collection_id

    second_link = repository.set_shot_collection(scene_id, created.id, next_collection_id)
    assert second_link is not None
    assert second_link.collection_id == initial_collection_id

    stored = repository.get_shot(scene_id, created.id)
    assert stored is not None
    assert stored.collection_id == initial_collection_id
