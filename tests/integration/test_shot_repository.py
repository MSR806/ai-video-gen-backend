from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.shot import ShotCreateInput, ShotUpdateInput
from ai_video_gen_backend.infrastructure.db.models import (
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
