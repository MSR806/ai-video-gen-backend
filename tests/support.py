from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from ai_video_gen_backend.infrastructure.db.models import (
    CollectionItemModel,
    CollectionModel,
    ProjectModel,
    SceneModel,
)


def seed_baseline_data(session: Session) -> dict[str, UUID]:
    project_id = uuid4()
    collection_id = uuid4()
    item_id = uuid4()
    scene_id = uuid4()

    session.add(
        ProjectModel(
            id=project_id,
            name='Seed Project',
            description='Seed project for tests',
            status='draft',
        )
    )
    session.add(
        CollectionModel(
            id=collection_id,
            project_id=project_id,
            name='Seed Collection',
            tag='seed',
            description='Seed collection for tests',
        )
    )
    session.add(
        CollectionItemModel(
            id=item_id,
            project_id=project_id,
            collection_id=collection_id,
            media_type='image',
            name='Seed Item',
            description='Seed item for tests',
            url='https://example.com/seed.jpg',
            metadata_json={
                'width': 1920,
                'height': 1080,
                'format': 'jpg',
                'thumbnailUrl': 'https://example.com/seed-item-thumb.jpg',
            },
            generation_source='upload',
        )
    )
    session.add(
        SceneModel(
            id=scene_id,
            project_id=project_id,
            name='Scene 1',
            scene_number=1,
            content_json={'text': 'Opening scene'},
        )
    )

    session.commit()

    return {
        'project_id': project_id,
        'collection_id': collection_id,
        'item_id': item_id,
        'scene_id': scene_id,
    }
