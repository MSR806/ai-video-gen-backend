from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.collection_item import CollectionItemCreationPayload
from ai_video_gen_backend.infrastructure.db.models import CollectionModel, ProjectModel
from ai_video_gen_backend.infrastructure.repositories import CollectionItemSqlRepository


def test_collection_item_repository_maps_storage_fields(db_session: Session) -> None:
    project_id = uuid4()
    collection_id = uuid4()

    db_session.add(
        ProjectModel(
            id=project_id,
            name='Project',
            description='Project for storage mapping',
            status='draft',
        )
    )
    db_session.add(
        CollectionModel(
            id=collection_id,
            project_id=project_id,
            name='Collection',
            tag='ref',
            description='Collection for storage mapping',
        )
    )
    db_session.commit()

    repository = CollectionItemSqlRepository(db_session)
    payload = CollectionItemCreationPayload(
        project_id=project_id,
        collection_id=collection_id,
        media_type='image',
        name='Uploaded Asset',
        description='Stored in object storage',
        url='http://localhost:9000/ai-video-gen-media/key.jpg',
        metadata={'width': 100, 'height': 200, 'format': 'jpg', 'thumbnailUrl': 'thumb'},
        generation_source='upload',
        storage_provider='s3',
        storage_bucket='ai-video-gen-media',
        storage_key='projects/p/collections/c/key.jpg',
        mime_type='image/jpeg',
        size_bytes=1234,
    )

    created = repository.create_item(payload)
    fetched = repository.get_item_by_id(created.id)

    assert fetched is not None
    assert fetched.storage_provider == 's3'
    assert fetched.storage_bucket == 'ai-video-gen-media'
    assert fetched.storage_key == 'projects/p/collections/c/key.jpg'
    assert fetched.mime_type == 'image/jpeg'
    assert fetched.size_bytes == 1234
    assert fetched.run_id is None


def test_collection_item_repository_delete_item_removes_record(db_session: Session) -> None:
    project_id = uuid4()
    collection_id = uuid4()

    db_session.add(
        ProjectModel(
            id=project_id,
            name='Project',
            description='Project for delete mapping',
            status='draft',
        )
    )
    db_session.add(
        CollectionModel(
            id=collection_id,
            project_id=project_id,
            name='Collection',
            tag='ref',
            description='Collection for delete mapping',
        )
    )
    db_session.commit()

    repository = CollectionItemSqlRepository(db_session)
    created = repository.create_item(
        CollectionItemCreationPayload(
            project_id=project_id,
            collection_id=collection_id,
            media_type='image',
            name='Delete Me',
            description='Delete candidate',
            url='http://localhost:9000/ai-video-gen-media/delete.jpg',
            metadata={'width': 100, 'height': 100, 'format': 'jpg', 'thumbnailUrl': ''},
            generation_source='upload',
        )
    )

    deleted = repository.delete_item(created.id)
    missing = repository.get_item_by_id(created.id)

    assert deleted is True
    assert missing is None
    assert repository.delete_item(uuid4()) is False
