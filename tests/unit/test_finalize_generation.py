from __future__ import annotations

from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.generation.finalize_generation import (
    GenerationFinalizationError,
    GenerationFinalizer,
)
from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    CollectionItemCreationPayload,
    JsonValue,
    StorageError,
    StoredObject,
    VideoThumbnailGenerationError,
)
from ai_video_gen_backend.domain.generation import (
    GenerationRun,
    GenerationRunOutput,
    MediaDownloadError,
)


class FakeCollectionItemRepository:
    def __init__(self, *, linked_item: CollectionItem | None) -> None:
        self.linked_item = linked_item
        self.ready_calls: list[dict[str, object]] = []
        self.failed_calls: list[dict[str, object]] = []

    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]:
        del collection_id
        return []

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None:
        del item_id
        return None

    def get_items_by_run_id(self, run_id: UUID) -> list[CollectionItem]:
        del run_id
        return [self.linked_item] if self.linked_item is not None else []

    def get_item_by_generation_run_output_id(
        self, generation_run_output_id: UUID
    ) -> CollectionItem | None:
        del generation_run_output_id
        return self.linked_item

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem:
        del payload
        raise NotImplementedError

    def delete_item(self, item_id: UUID) -> bool:
        del item_id
        return False

    def mark_generated_item_ready(
        self,
        *,
        item_id: UUID,
        url: str,
        metadata: dict[str, JsonValue],
        storage_provider: str | None,
        storage_bucket: str | None,
        storage_key: str | None,
        mime_type: str | None,
        size_bytes: int | None,
    ) -> CollectionItem | None:
        self.ready_calls.append(
            {
                'item_id': item_id,
                'url': url,
                'metadata': metadata,
                'storage_provider': storage_provider,
                'storage_bucket': storage_bucket,
                'storage_key': storage_key,
                'mime_type': mime_type,
                'size_bytes': size_bytes,
            }
        )
        if self.linked_item is None:
            return None
        now = datetime.now(UTC)
        linked = self.linked_item
        return CollectionItem(
            id=linked.id,
            project_id=linked.project_id,
            collection_id=linked.collection_id,
            media_type=linked.media_type,
            status='READY',
            name=linked.name,
            description=linked.description,
            url=url,
            metadata=dict(metadata),
            generation_source=linked.generation_source,
            generation_error_message=None,
            created_at=linked.created_at,
            updated_at=now,
            run_id=linked.run_id,
            generation_run_output_id=linked.generation_run_output_id,
            storage_provider=storage_provider,
            storage_bucket=storage_bucket,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )

    def mark_generated_item_failed(
        self, *, item_id: UUID, error_message: str
    ) -> CollectionItem | None:
        self.failed_calls.append({'item_id': item_id, 'error_message': error_message})
        if self.linked_item is None:
            return None
        now = datetime.now(UTC)
        linked = self.linked_item
        return CollectionItem(
            id=linked.id,
            project_id=linked.project_id,
            collection_id=linked.collection_id,
            media_type=linked.media_type,
            status='FAILED',
            name=linked.name,
            description=linked.description,
            url=linked.url,
            metadata=linked.metadata,
            generation_source=linked.generation_source,
            generation_error_message=error_message,
            created_at=linked.created_at,
            updated_at=now,
            run_id=linked.run_id,
            generation_run_output_id=linked.generation_run_output_id,
            storage_provider=linked.storage_provider,
            storage_bucket=linked.storage_bucket,
            storage_key=linked.storage_key,
            mime_type=linked.mime_type,
            size_bytes=linked.size_bytes,
        )

    def set_item_favorite(self, *, item_id: UUID, is_favorite: bool) -> CollectionItem | None:
        del item_id, is_favorite
        return None


class FakeGenerationRunRepository:
    def __init__(self) -> None:
        self.ready_calls: list[dict[str, object]] = []
        self.failed_calls: list[dict[str, object]] = []

    def create_run(
        self,
        *,
        project_id: UUID,
        operation_key: str,
        provider: str,
        model_key: str,
        endpoint_id: str,
        requested_output_count: int,
        inputs_json: dict[str, object],
        idempotency_key: str | None,
    ) -> GenerationRun:
        del (
            project_id,
            operation_key,
            provider,
            model_key,
            endpoint_id,
            requested_output_count,
            inputs_json,
            idempotency_key,
        )
        raise NotImplementedError

    def create_run_outputs(self, *, run_id: UUID, output_count: int) -> list[GenerationRunOutput]:
        del run_id, output_count
        raise NotImplementedError

    def get_run_by_id(self, run_id: UUID) -> GenerationRun | None:
        del run_id
        return None

    def get_run_by_provider_request_id(self, provider_request_id: str) -> GenerationRun | None:
        del provider_request_id
        return None

    def get_run_by_idempotency_key(
        self,
        *,
        project_id: UUID,
        idempotency_key: str,
    ) -> GenerationRun | None:
        del project_id, idempotency_key
        return None

    def list_outputs_by_run_id(self, run_id: UUID) -> list[GenerationRunOutput]:
        del run_id
        return []

    def mark_run_submitted(self, run_id: UUID, *, provider_request_id: str) -> GenerationRun:
        del run_id, provider_request_id
        raise NotImplementedError

    def mark_run_in_progress(self, run_id: UUID) -> GenerationRun:
        del run_id
        raise NotImplementedError

    def mark_run_succeeded(
        self, run_id: UUID, *, provider_response_json: dict[str, object]
    ) -> GenerationRun:
        del run_id, provider_response_json
        raise NotImplementedError

    def mark_run_partial_failed(
        self, run_id: UUID, *, provider_response_json: dict[str, object], error_message: str
    ) -> GenerationRun:
        del run_id, provider_response_json, error_message
        raise NotImplementedError

    def mark_run_failed(
        self,
        run_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun:
        del run_id, error_code, error_message, provider_response_json
        raise NotImplementedError

    def mark_run_cancelled(
        self,
        run_id: UUID,
        *,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun:
        del run_id, error_message, provider_response_json
        raise NotImplementedError

    def mark_output_ready(
        self,
        *,
        output_id: UUID,
        provider_output_json: dict[str, object],
        stored_output_json: dict[str, object],
    ) -> GenerationRunOutput:
        self.ready_calls.append(
            {
                'output_id': output_id,
                'provider_output_json': provider_output_json,
                'stored_output_json': stored_output_json,
            }
        )
        now = datetime.now(UTC)
        return GenerationRunOutput(
            id=output_id,
            run_id=uuid4(),
            output_index=0,
            status='READY',
            provider_output_json=provider_output_json,
            stored_output_json=stored_output_json,
            error_code=None,
            error_message=None,
            created_at=now,
            updated_at=now,
        )

    def mark_output_failed(
        self,
        *,
        output_id: UUID,
        error_code: str,
        error_message: str,
        provider_output_json: dict[str, object] | None = None,
    ) -> GenerationRunOutput:
        self.failed_calls.append(
            {
                'output_id': output_id,
                'error_code': error_code,
                'error_message': error_message,
                'provider_output_json': provider_output_json,
            }
        )
        now = datetime.now(UTC)
        return GenerationRunOutput(
            id=output_id,
            run_id=uuid4(),
            output_index=0,
            status='FAILED',
            provider_output_json=provider_output_json,
            stored_output_json=None,
            error_code=error_code,
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )


class FakeObjectStorage:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def upload_object(
        self,
        *,
        key: str,
        content_type: str,
        body: BinaryIO,
        size_bytes: int,
    ) -> StoredObject:
        body.seek(0)
        payload = body.read()
        self.calls.append(
            {
                'key': key,
                'content_type': content_type,
                'size_bytes': size_bytes,
                'payload': payload,
            }
        )
        if self.fail:
            raise StorageError('failed')
        return StoredObject(
            provider='s3',
            bucket='bucket',
            key=key,
            url=f'https://cdn.test/{key}',
            mime_type=content_type,
            size_bytes=size_bytes,
        )

    def delete_object(self, *, key: str) -> None:
        del key


class FakeMediaDownloader:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def download(self, url: str, *, max_bytes: int) -> tuple[bytes, str]:
        del max_bytes
        if self.fail:
            raise MediaDownloadError('download failed')
        if url.endswith('.mp4'):
            return (b'video-bytes', 'video/mp4')
        return (b'image-bytes', 'image/png')


class FakeVideoThumbnailGenerator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def extract_first_frame(self, *, video_stream: BinaryIO) -> bytes:
        video_stream.seek(0)
        _ = video_stream.read()
        if self.fail:
            raise VideoThumbnailGenerationError('thumb failed')
        return b'thumb-bytes'


def _linked_item(output_id: UUID) -> CollectionItem:
    now = datetime.now(UTC)
    return CollectionItem(
        id=uuid4(),
        project_id=uuid4(),
        collection_id=uuid4(),
        media_type='image',
        status='GENERATING',
        name='Placeholder',
        description='pending',
        url=None,
        metadata={'thumbnailUrl': '', 'width': 0, 'height': 0, 'format': 'png'},
        generation_source='fal',
        generation_error_message=None,
        created_at=now,
        updated_at=now,
        run_id=uuid4(),
        generation_run_output_id=output_id,
    )


def _build_finalizer(
    *,
    collection_repo: FakeCollectionItemRepository,
    run_repo: FakeGenerationRunRepository | None = None,
    storage: FakeObjectStorage | None = None,
    downloader: FakeMediaDownloader | None = None,
    thumbnail: FakeVideoThumbnailGenerator | None = None,
) -> tuple[GenerationFinalizer, FakeGenerationRunRepository]:
    run_repository = run_repo or FakeGenerationRunRepository()
    finalizer = GenerationFinalizer(
        collection_item_repository=collection_repo,
        generation_run_repository=run_repository,
        object_storage=storage or FakeObjectStorage(),
        media_downloader=downloader or FakeMediaDownloader(),
        video_thumbnail_generator=thumbnail or FakeVideoThumbnailGenerator(),
        max_download_bytes=1024 * 1024,
    )
    return finalizer, run_repository


def test_finalize_output_success_marks_item_and_output_ready() -> None:
    output_id = uuid4()
    collection_repo = FakeCollectionItemRepository(linked_item=_linked_item(output_id))
    finalizer, run_repo = _build_finalizer(collection_repo=collection_repo)

    finalizer.finalize_output_success(
        output_id=output_id,
        output={
            'index': 0,
            'media_type': 'image',
            'provider_url': 'https://provider.test/image.png',
            'metadata': {},
        },
    )

    assert len(collection_repo.ready_calls) == 1
    assert str(collection_repo.ready_calls[0]['url']).startswith('https://cdn.test/generated/')
    assert len(run_repo.ready_calls) == 1
    assert run_repo.ready_calls[0]['output_id'] == output_id


def test_finalize_output_failure_marks_item_and_output_failed() -> None:
    output_id = uuid4()
    collection_repo = FakeCollectionItemRepository(linked_item=_linked_item(output_id))
    finalizer, run_repo = _build_finalizer(collection_repo=collection_repo)

    finalizer.finalize_output_failure(
        output_id=output_id,
        error_code='provider_generation_failed',
        error_message='provider failed',
    )

    assert len(collection_repo.failed_calls) == 1
    assert collection_repo.failed_calls[0]['error_message'] == 'provider failed'
    assert len(run_repo.failed_calls) == 1
    assert run_repo.failed_calls[0]['error_code'] == 'provider_generation_failed'


def test_finalize_output_success_raises_when_linked_item_missing() -> None:
    output_id = uuid4()
    collection_repo = FakeCollectionItemRepository(linked_item=None)
    finalizer, _ = _build_finalizer(collection_repo=collection_repo)

    with pytest.raises(GenerationFinalizationError):
        finalizer.finalize_output_success(
            output_id=output_id,
            output={
                'index': 0,
                'media_type': 'image',
                'provider_url': 'https://provider.test/image.png',
                'metadata': {},
            },
        )


def test_finalize_output_success_raises_on_blank_provider_url() -> None:
    output_id = uuid4()
    collection_repo = FakeCollectionItemRepository(linked_item=_linked_item(output_id))
    finalizer, _ = _build_finalizer(collection_repo=collection_repo)

    with pytest.raises(GenerationFinalizationError, match='valid output URL'):
        finalizer.finalize_output_success(
            output_id=output_id,
            output={
                'index': 0,
                'media_type': 'image',
                'provider_url': '   ',
                'metadata': {},
            },
        )


def test_finalize_output_success_raises_when_download_fails() -> None:
    output_id = uuid4()
    collection_repo = FakeCollectionItemRepository(linked_item=_linked_item(output_id))
    finalizer, _ = _build_finalizer(
        collection_repo=collection_repo,
        downloader=FakeMediaDownloader(fail=True),
    )

    with pytest.raises(GenerationFinalizationError, match='download failed'):
        finalizer.finalize_output_success(
            output_id=output_id,
            output={
                'index': 0,
                'media_type': 'image',
                'provider_url': 'https://provider.test/image.png',
                'metadata': {},
            },
        )


def test_finalize_output_success_raises_when_storage_upload_fails() -> None:
    output_id = uuid4()
    collection_repo = FakeCollectionItemRepository(linked_item=_linked_item(output_id))
    finalizer, _ = _build_finalizer(
        collection_repo=collection_repo,
        storage=FakeObjectStorage(fail=True),
    )

    with pytest.raises(GenerationFinalizationError, match='Failed to store generated output'):
        finalizer.finalize_output_success(
            output_id=output_id,
            output={
                'index': 0,
                'media_type': 'image',
                'provider_url': 'https://provider.test/image.png',
                'metadata': {},
            },
        )


def test_finalize_video_output_falls_back_to_empty_thumbnail_when_generation_fails() -> None:
    output_id = uuid4()
    collection_repo = FakeCollectionItemRepository(linked_item=_linked_item(output_id))
    finalizer, run_repo = _build_finalizer(
        collection_repo=collection_repo,
        thumbnail=FakeVideoThumbnailGenerator(fail=True),
    )

    finalizer.finalize_output_success(
        output_id=output_id,
        output={
            'index': 0,
            'media_type': 'video',
            'provider_url': 'https://provider.test/video.mp4',
            'metadata': {},
        },
    )

    metadata = collection_repo.ready_calls[0]['metadata']
    assert isinstance(metadata, dict)
    assert metadata.get('thumbnailUrl') == ''

    stored_output = run_repo.ready_calls[0]['stored_output_json']
    assert isinstance(stored_output, dict)
    assert stored_output.get('thumbnailUrl') == ''
