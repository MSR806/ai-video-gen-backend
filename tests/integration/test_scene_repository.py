from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.scene import Scene
from ai_video_gen_backend.infrastructure.db.models import ProjectModel
from ai_video_gen_backend.infrastructure.repositories import SceneSqlRepository


def test_scene_repository_bulk_replace_is_atomic_per_project(db_session: Session) -> None:
    project_id = uuid4()
    db_session.add(
        ProjectModel(
            id=project_id,
            name='Project',
            description='Project for scene repository test',
            status='draft',
        )
    )
    db_session.commit()

    repository = SceneSqlRepository(db_session)

    first_batch = [
        Scene(
            id=uuid4(),
            project_id=project_id,
            name='Scene A',
            scene_number=1,
            content={'text': 'A'},
        ),
        Scene(
            id=uuid4(),
            project_id=project_id,
            name='Scene B',
            scene_number=2,
            content={'text': 'B'},
        ),
    ]
    repository.bulk_replace(project_id, first_batch)

    second_batch = [
        Scene(
            id=uuid4(),
            project_id=project_id,
            name='Scene Z',
            scene_number=1,
            content={'text': 'Z'},
        )
    ]
    repository.bulk_replace(project_id, second_batch)

    scenes = repository.get_scenes_by_project_id(project_id)
    assert len(scenes) == 1
    assert scenes[0].name == 'Scene Z'
    assert scenes[0].scene_number == 1
