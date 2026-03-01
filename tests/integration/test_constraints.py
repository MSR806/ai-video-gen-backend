from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_video_gen_backend.infrastructure.db.models import (
    CollectionItemModel,
    CollectionModel,
    ProjectModel,
    SceneModel,
)


def test_unique_scene_number_constraint(db_session: Session) -> None:
    project_id = uuid4()
    db_session.add(
        ProjectModel(
            id=project_id,
            name='Project',
            description='Project for constraint test',
            status='draft',
        )
    )
    db_session.commit()

    db_session.add_all(
        [
            SceneModel(
                id=uuid4(),
                project_id=project_id,
                name='One',
                scene_number=1,
                content_json={'text': 'One'},
            ),
            SceneModel(
                id=uuid4(),
                project_id=project_id,
                name='Duplicate',
                scene_number=1,
                content_json={'text': 'Duplicate'},
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_collection_item_project_collection_consistency_constraint(db_session: Session) -> None:
    project_a = uuid4()
    project_b = uuid4()
    collection_id = uuid4()

    db_session.add_all(
        [
            ProjectModel(
                id=project_a,
                name='Project A',
                description='Project A',
                status='draft',
            ),
            ProjectModel(
                id=project_b,
                name='Project B',
                description='Project B',
                status='draft',
            ),
            CollectionModel(
                id=collection_id,
                project_id=project_a,
                name='Collection',
                tag='tag',
                description='Collection description',
            ),
        ]
    )
    db_session.commit()

    db_session.add(
        CollectionItemModel(
            id=uuid4(),
            project_id=project_b,
            collection_id=collection_id,
            media_type='image',
            name='Broken Link',
            description='Should fail due to collection/project mismatch',
            url='https://example.com/fail.jpg',
            metadata_json={'width': 1, 'height': 1, 'format': 'jpg'},
            generation_source='upload',
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
