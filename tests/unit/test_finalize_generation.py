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
from ai_video_gen_backend.domain.generation import GenerationJob, MediaDownloadError
from ai_video_gen_backend.domain.types import JsonObject


class FakeCollectionItemRepository:
    def __init__(
        self, *, ready_returns_none: bool = False, failed_returns_none: bool = False
    ) -> None:
        self.ready_returns_none = ready_returns_none
        self.failed_returns_none = failed_returns_none
        self.last_ready_call: dict[str, object] | None = None
        self.last_failed_call: dict[str, object] | None = None

    def get_items_by_collection_id(self, collection_id: UUID) -> list[CollectionItem]:
        del collection_id
        return []

    def get_item_by_id(self, item_id: UUID) -> CollectionItem | None:
        del item_id
        return None

    def create_item(self, payload: CollectionItemCreationPayload) -> CollectionItem:
        del payload
        raise NotImplementedError

    def delete_item(self, item_id: UUID) -> bool:
        del item_id
        return False

    def assign_job_id(self, *, item_id: UUID, job_id: UUID) -> CollectionItem | None:
        del item_id, job_id
        return None

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
        self.last_ready_call = {
            'item_id': item_id,
            'url': url,
            'metadata': metadata,
            'storage_provider': storage_provider,
            'storage_bucket': storage_bucket,
            'storage_key': storage_key,
            'mime_type': mime_type,
            'size_bytes': size_bytes,
        }
        if self.ready_returns_none:
            return None

        now = datetime.now(UTC)
        return CollectionItem(
            id=item_id,
            project_id=uuid4(),
            collection_id=uuid4(),
            media_type='image',
            status='READY',
            name='Generated',
            description='desc',
            url=url,
            metadata=dict(metadata),
            generation_source='fal',
            generation_error_message=None,
            created_at=now,
            updated_at=now,
            storage_provider=storage_provider,
            storage_bucket=storage_bucket,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )

    def mark_generated_item_failed(
        self,
        *,
        item_id: UUID,
        error_message: str,
    ) -> CollectionItem | None:
        self.last_failed_call = {
            'item_id': item_id,
            'error_message': error_message,
        }
        if self.failed_returns_none:
            return None

        now = datetime.now(UTC)
        return CollectionItem(
            id=item_id,
            project_id=uuid4(),
            collection_id=uuid4(),
            media_type='image',
            status='FAILED',
            name='Generated',
            description='desc',
            url=None,
            metadata={'thumbnailUrl': ''},
            generation_source='fal',
            generation_error_message=error_message,
            created_at=now,
            updated_at=now,
        )


class FakeGenerationJobRepository:
    def __init__(self) -> None:
        self.succeeded_calls: list[dict[str, object]] = []
        self.failed_calls: list[dict[str, object]] = []

    def create_job(
        self,
        *,
        project_id: UUID,
        collection_id: UUID,
        collection_item_id: UUID,
        operation_key: str,
        provider: str,
        model_key: str,
        endpoint_id: str,
        inputs_json: dict[str, object],
        idempotency_key: str | None,
    ) -> GenerationJob:
        del (
            project_id,
            collection_id,
            collection_item_id,
            operation_key,
            provider,
            model_key,
            endpoint_id,
            inputs_json,
            idempotency_key,
        )
        raise NotImplementedError

    def get_by_id(self, job_id: UUID) -> GenerationJob | None:
        del job_id
        return None

    def get_by_provider_request_id(self, provider_request_id: str) -> GenerationJob | None:
        del provider_request_id
        return None

    def get_by_idempotency_key(
        self,
        *,
        project_id: UUID,
        collection_id: UUID,
        idempotency_key: str,
    ) -> GenerationJob | None:
        del project_id, collection_id, idempotency_key
        return None

    def mark_submitted(self, job_id: UUID, *, provider_request_id: str) -> GenerationJob:
        del job_id, provider_request_id
        raise NotImplementedError

    def mark_in_progress(self, job_id: UUID) -> GenerationJob:
        del job_id
        raise NotImplementedError

    def mark_succeeded(
        self,
        job_id: UUID,
        *,
        provider_response_json: dict[str, object],
        outputs_json: list[dict[str, object]],
    ) -> GenerationJob:
        self.succeeded_calls.append(
            {
                'job_id': job_id,
                'provider_response_json': provider_response_json,
                'outputs_json': outputs_json,
            }
        )
        now = datetime.now(UTC)
        return GenerationJob(
            id=job_id,
            project_id=uuid4(),
            collection_id=uuid4(),
            collection_item_id=uuid4(),
            operation_key='text_to_image',
            provider='fal',
            model_key='nano_banana',
            endpoint_id='fal-ai/nano-banana',
            status='SUCCEEDED',
            inputs_json={},
            outputs_json=[{'provider_url': 'https://provider.test/image.png'}],
            provider_request_id='req-123',
            provider_response_json=provider_response_json,
            idempotency_key=None,
            error_code=None,
            error_message=None,
            submitted_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )

    def mark_failed(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationJob:
        self.failed_calls.append(
            {
                'job_id': job_id,
                'error_code': error_code,
                'error_message': error_message,
                'provider_response_json': provider_response_json,
            }
        )
        now = datetime.now(UTC)
        return GenerationJob(
            id=job_id,
            project_id=uuid4(),
            collection_id=uuid4(),
            collection_item_id=uuid4(),
            operation_key='text_to_image',
            provider='fal',
            model_key='nano_banana',
            endpoint_id='fal-ai/nano-banana',
            status='FAILED',
            inputs_json={},
            outputs_json=[],
            provider_request_id='req-123',
            provider_response_json=provider_response_json,
            idempotency_key=None,
            error_code=error_code,
            error_message=error_message,
            submitted_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )


class FakeObjectStorage:
    def __init__(self, *, fail_on_upload_number: int | None = None) -> None:
        self.fail_on_upload_number = fail_on_upload_number
        self.upload_calls: list[dict[str, object]] = []

    def upload_object(
        self,
        *,
        key: str,
        content_type: str,
        body: BinaryIO,
        size_bytes: int,
    ) -> StoredObject:
        upload_number = len(self.upload_calls) + 1
        body.seek(0)
        payload = body.read()
        self.upload_calls.append(
            {
                'key': key,
                'content_type': content_type,
                'size_bytes': size_bytes,
                'payload': payload,
            }
        )

        if self.fail_on_upload_number == upload_number:
            raise StorageError('upload failed')

        return StoredObject(
            provider='s3',
            bucket='media',
            key=key,
            url=f'https://storage.test/{key}',
            mime_type=content_type,
            size_bytes=size_bytes,
        )

    def delete_object(self, *, key: str) -> None:
        del key


class FakeMediaDownloader:
    def __init__(
        self,
        *,
        downloaded: bytes = b'asset',
        content_type: str = 'image/png',
        error: Exception | None = None,
    ) -> None:
        self.downloaded = downloaded
        self.content_type = content_type
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def download(self, url: str, *, max_bytes: int) -> tuple[bytes, str]:
        self.calls.append((url, max_bytes))
        if self.error is not None:
            raise self.error
        return self.downloaded, self.content_type


class FakeVideoThumbnailGenerator:
    def __init__(
        self,
        *,
        output: bytes = b'thumbnail',
        error: Exception | None = None,
    ) -> None:
        self.output = output
        self.error = error
        self.calls: list[bytes] = []

    def extract_first_frame(self, *, video_stream: BinaryIO) -> bytes:
        video_stream.seek(0)
        payload = video_stream.read()
        self.calls.append(payload)
        if self.error is not None:
            raise self.error
        return self.output


def _build_finalizer(
    *,
    collection_repo: FakeCollectionItemRepository | None = None,
    job_repo: FakeGenerationJobRepository | None = None,
    object_storage: FakeObjectStorage | None = None,
    downloader: FakeMediaDownloader | None = None,
    thumbnail_generator: FakeVideoThumbnailGenerator | None = None,
) -> tuple[
    GenerationFinalizer,
    FakeCollectionItemRepository,
    FakeGenerationJobRepository,
    FakeObjectStorage,
    FakeMediaDownloader,
    FakeVideoThumbnailGenerator,
]:
    collection_repo_value = collection_repo or FakeCollectionItemRepository()
    job_repo_value = job_repo or FakeGenerationJobRepository()
    object_storage_value = object_storage or FakeObjectStorage()
    downloader_value = downloader or FakeMediaDownloader()
    thumbnail_generator_value = thumbnail_generator or FakeVideoThumbnailGenerator()

    finalizer = GenerationFinalizer(
        collection_item_repository=collection_repo_value,
        generation_job_repository=job_repo_value,
        object_storage=object_storage_value,
        media_downloader=downloader_value,
        video_thumbnail_generator=thumbnail_generator_value,
        max_download_bytes=1024,
    )
    return (
        finalizer,
        collection_repo_value,
        job_repo_value,
        object_storage_value,
        downloader_value,
        thumbnail_generator_value,
    )


def test_finalize_success_image_happy_path_marks_item_ready_and_job_succeeded() -> None:
    (
        finalizer,
        collection_repo,
        job_repo,
        object_storage,
        downloader,
        _,
    ) = _build_finalizer()

    job_id = uuid4()
    item_id = uuid4()
    provider_response_json: JsonObject = {'status': 'COMPLETED'}
    outputs_json: list[dict[str, object]] = [{'provider_url': 'https://provider.test/image.png'}]

    finalizer.finalize_success(
        job_id=job_id,
        item_id=item_id,
        output={'provider_url': 'https://provider.test/image.png'},
        provider_response_json=provider_response_json,
        outputs_json=outputs_json,
    )

    assert downloader.calls == [('https://provider.test/image.png', 1024)]
    assert len(object_storage.upload_calls) == 1
    assert object_storage.upload_calls[0]['key'] == f'generated/{item_id}.png'
    assert collection_repo.last_ready_call is not None
    assert collection_repo.last_ready_call['url'] == f'https://storage.test/generated/{item_id}.png'
    metadata = collection_repo.last_ready_call['metadata']
    assert isinstance(metadata, dict)
    assert metadata['format'] == 'png'
    assert metadata['thumbnailUrl'] == f'https://storage.test/generated/{item_id}.png'
    assert metadata['sizeBytes'] == len(b'asset')
    assert len(job_repo.succeeded_calls) == 1
    assert job_repo.succeeded_calls[0]['job_id'] == job_id


def test_finalize_success_video_happy_path_uploads_video_and_thumbnail() -> None:
    downloader = FakeMediaDownloader(downloaded=b'video-bytes', content_type='video/mp4')
    (
        finalizer,
        collection_repo,
        _,
        object_storage,
        _,
        thumbnail_generator,
    ) = _build_finalizer(downloader=downloader)

    item_id = uuid4()
    finalizer.finalize_success(
        job_id=uuid4(),
        item_id=item_id,
        output={'provider_url': 'https://provider.test/video.mp4', 'media_type': 'video'},
        provider_response_json={'status': 'COMPLETED'},
        outputs_json=[{'provider_url': 'https://provider.test/video.mp4'}],
    )

    assert len(object_storage.upload_calls) == 2
    assert object_storage.upload_calls[0]['key'] == f'generated/{item_id}.mp4'
    assert object_storage.upload_calls[1]['key'] == f'generated/{item_id}-thumb.jpg'
    assert thumbnail_generator.calls == [b'video-bytes']
    assert collection_repo.last_ready_call is not None
    metadata = collection_repo.last_ready_call['metadata']
    assert isinstance(metadata, dict)
    assert metadata['format'] == 'mp4'
    assert metadata['thumbnailUrl'] == f'https://storage.test/generated/{item_id}-thumb.jpg'


@pytest.mark.parametrize(
    ('output',),
    [
        ({},),
        ({'provider_url': ''},),
        ({'provider_url': '   '},),
        ({'provider_url': 123},),
    ],
)
def test_finalize_success_raises_when_provider_url_is_invalid(output: dict[str, object]) -> None:
    finalizer, _, _, _, _, _ = _build_finalizer()

    with pytest.raises(GenerationFinalizationError, match='valid output URL'):
        finalizer.finalize_success(
            job_id=uuid4(),
            item_id=uuid4(),
            output=output,
            provider_response_json={},
            outputs_json=[],
        )


def test_finalize_success_wraps_downloader_error() -> None:
    finalizer, _, _, _, _, _ = _build_finalizer(
        downloader=FakeMediaDownloader(error=MediaDownloadError('download exploded'))
    )

    with pytest.raises(GenerationFinalizationError, match='download exploded'):
        finalizer.finalize_success(
            job_id=uuid4(),
            item_id=uuid4(),
            output={'provider_url': 'https://provider.test/image.png'},
            provider_response_json={},
            outputs_json=[],
        )


def test_finalize_success_wraps_storage_error() -> None:
    finalizer, _, _, _, _, _ = _build_finalizer(
        object_storage=FakeObjectStorage(fail_on_upload_number=1)
    )

    with pytest.raises(GenerationFinalizationError, match='Failed to store generated output'):
        finalizer.finalize_success(
            job_id=uuid4(),
            item_id=uuid4(),
            output={'provider_url': 'https://provider.test/image.png'},
            provider_response_json={},
            outputs_json=[],
        )


def test_finalize_success_raises_when_collection_item_missing() -> None:
    finalizer, _, _, _, _, _ = _build_finalizer(
        collection_repo=FakeCollectionItemRepository(ready_returns_none=True)
    )

    with pytest.raises(GenerationFinalizationError, match='Collection item was not found'):
        finalizer.finalize_success(
            job_id=uuid4(),
            item_id=uuid4(),
            output={'provider_url': 'https://provider.test/image.png'},
            provider_response_json={},
            outputs_json=[],
        )


def test_finalize_failure_marks_item_and_job_failed() -> None:
    finalizer, collection_repo, job_repo, _, _, _ = _build_finalizer()
    job_id = uuid4()
    item_id = uuid4()

    finalizer.finalize_failure(
        job_id=job_id,
        item_id=item_id,
        error_code='provider_failed',
        error_message='provider failed',
        provider_response_json={'status': 'FAILED'},
    )

    assert collection_repo.last_failed_call == {
        'item_id': item_id,
        'error_message': 'provider failed',
    }
    assert len(job_repo.failed_calls) == 1
    assert job_repo.failed_calls[0]['job_id'] == job_id
    assert job_repo.failed_calls[0]['error_code'] == 'provider_failed'


def test_finalize_failure_raises_when_collection_item_missing() -> None:
    finalizer, _, _, _, _, _ = _build_finalizer(
        collection_repo=FakeCollectionItemRepository(failed_returns_none=True)
    )

    with pytest.raises(GenerationFinalizationError, match='Collection item was not found'):
        finalizer.finalize_failure(
            job_id=uuid4(),
            item_id=uuid4(),
            error_code='provider_failed',
            error_message='provider failed',
        )


def test_format_from_content_type_handles_common_and_invalid_values() -> None:
    finalizer, _, _, _, _, _ = _build_finalizer()

    assert finalizer._format_from_content_type('image/jpeg') == 'jpg'
    assert finalizer._format_from_content_type('video/mp4; charset=binary') == 'mp4'
    assert finalizer._format_from_content_type('invalid') == 'png'
    assert finalizer._format_from_content_type('image/@@@') == 'png'


def test_resolve_media_type_prefers_output_field_then_content_type_fallback() -> None:
    finalizer, _, _, _, _, _ = _build_finalizer()

    assert (
        finalizer._resolve_media_type(output={'media_type': 'video'}, content_type='image/png')
        == 'video'
    )
    assert finalizer._resolve_media_type(output={}, content_type='video/mp4') == 'video'
    assert finalizer._resolve_media_type(output={}, content_type='image/png') == 'image'


def test_generate_video_thumbnail_returns_empty_when_extraction_fails() -> None:
    finalizer, _, _, _, _, _ = _build_finalizer(
        thumbnail_generator=FakeVideoThumbnailGenerator(
            error=VideoThumbnailGenerationError('thumbnail failed')
        )
    )

    assert finalizer._generate_video_thumbnail(item_id=uuid4(), video=b'video') == ''


def test_generate_video_thumbnail_returns_empty_when_upload_fails() -> None:
    finalizer, _, _, _, _, _ = _build_finalizer(
        object_storage=FakeObjectStorage(fail_on_upload_number=1)
    )

    assert finalizer._generate_video_thumbnail(item_id=uuid4(), video=b'video') == ''
