from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.scene import SceneCreateInput
from ai_video_gen_backend.infrastructure.db.models import ProjectModel
from ai_video_gen_backend.infrastructure.repositories import SceneSqlRepository


def test_scene_repository_insert_renumbers_existing_scenes(db_session: Session) -> None:
    project_id = uuid4()
    db_session.add(
        ProjectModel(
            id=project_id,
            name='Insert Project',
            description='Project for insert scene repository test',
            status='draft',
        )
    )
    db_session.commit()

    repository = SceneSqlRepository(db_session)
    repository.create_scene(
        project_id,
        SceneCreateInput(name='Scene 1', content={'text': 'One'}),
    )
    repository.create_scene(
        project_id,
        SceneCreateInput(name='Scene 2', content={'text': 'Two'}),
    )

    scenes = repository.create_scene(
        project_id,
        SceneCreateInput(position=2, name='Inserted', content={'text': 'Inserted'}),
    )

    assert [scene.scene_number for scene in scenes] == [1, 2, 3]
    assert [scene.name for scene in scenes] == ['Scene 1', 'Inserted', 'Scene 2']


def test_scene_repository_delete_renumbers_and_preserves_single_default(
    db_session: Session,
) -> None:
    project_id = uuid4()
    db_session.add(
        ProjectModel(
            id=project_id,
            name='Delete Project',
            description='Project for delete scene repository test',
            status='draft',
        )
    )
    db_session.commit()

    repository = SceneSqlRepository(db_session)
    initial_scenes = repository.create_scene(
        project_id,
        SceneCreateInput(name='Scene 1', content={'text': 'One'}),
    )
    second_scene = repository.create_scene(
        project_id,
        SceneCreateInput(name='Scene 2', content={'text': 'Two'}),
    )[1]

    deleted_middle = repository.delete_scene(project_id, second_scene.id)
    assert deleted_middle is not None
    assert [scene.scene_number for scene in deleted_middle] == [1]
    assert deleted_middle[0].name == initial_scenes[0].name

    deleted_last = repository.delete_scene(project_id, deleted_middle[0].id)
    assert deleted_last is not None
    assert len(deleted_last) == 1
    assert deleted_last[0].scene_number == 1
    assert deleted_last[0].name == 'Untitled Scene 1'


def test_scene_repository_sequence_keeps_contiguous_scene_numbers(db_session: Session) -> None:
    project_id = uuid4()
    db_session.add(
        ProjectModel(
            id=project_id,
            name='Sequence Project',
            description='Project for sequence scene repository test',
            status='draft',
        )
    )
    db_session.commit()

    repository = SceneSqlRepository(db_session)
    repository.create_scene(project_id, SceneCreateInput(name='A', content={'text': 'A'}))
    repository.create_scene(project_id, SceneCreateInput(name='B', content={'text': 'B'}))
    repository.create_scene(
        project_id, SceneCreateInput(position=2, name='C', content={'text': 'C'})
    )

    middle_scene = repository.get_scenes_by_project_id(project_id)[1]
    repository.delete_scene(project_id, middle_scene.id)

    final_scenes = repository.get_scenes_by_project_id(project_id)
    assert [scene.scene_number for scene in final_scenes] == [1, 2]
