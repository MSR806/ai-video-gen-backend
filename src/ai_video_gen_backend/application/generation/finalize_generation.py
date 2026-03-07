from __future__ import annotations

from io import BytesIO
from uuid import UUID

from ai_video_gen_backend.domain.collection_item import (
    CollectionItemRepositoryPort,
    ObjectStoragePort,
    StorageError,
    VideoThumbnailGenerationError,
    VideoThumbnailGeneratorPort,
)
from ai_video_gen_backend.domain.generation import (
    GenerationRunRepositoryPort,
    MediaDownloaderPort,
    MediaDownloadError,
)
from ai_video_gen_backend.domain.types import JsonObject


class GenerationFinalizationError(Exception):
    """Raised when finalization of generated media fails."""


class GenerationFinalizer:
    def __init__(
        self,
        *,
        collection_item_repository: CollectionItemRepositoryPort,
        generation_run_repository: GenerationRunRepositoryPort,
        object_storage: ObjectStoragePort,
        media_downloader: MediaDownloaderPort,
        video_thumbnail_generator: VideoThumbnailGeneratorPort,
        max_download_bytes: int,
    ) -> None:
        self._collection_item_repository = collection_item_repository
        self._generation_run_repository = generation_run_repository
        self._object_storage = object_storage
        self._media_downloader = media_downloader
        self._video_thumbnail_generator = video_thumbnail_generator
        self._max_download_bytes = max_download_bytes

    def finalize_output_success(
        self,
        *,
        output_id: UUID,
        output: dict[str, object],
    ) -> None:
        collection_item = self._collection_item_repository.get_item_by_generation_run_output_id(
            output_id
        )
        if collection_item is None:
            raise GenerationFinalizationError(
                f'Collection item linked to output {output_id} was not found while finalizing'
            )

        provider_url = output.get('provider_url')
        if not isinstance(provider_url, str) or len(provider_url.strip()) == 0:
            raise GenerationFinalizationError(
                'Provider response did not include a valid output URL'
            )

        try:
            downloaded, content_type = self._media_downloader.download(
                provider_url, max_bytes=self._max_download_bytes
            )
        except MediaDownloadError as exc:
            raise GenerationFinalizationError(str(exc)) from exc

        storage_key = self._build_storage_key(item_id=collection_item.id, content_type=content_type)

        try:
            stored_object = self._object_storage.upload_object(
                key=storage_key,
                content_type=content_type,
                body=BytesIO(downloaded),
                size_bytes=len(downloaded),
            )
        except StorageError as exc:
            raise GenerationFinalizationError('Failed to store generated output') from exc

        media_type = self._resolve_media_type(output=output, content_type=content_type)
        thumbnail_url = stored_object.url
        if media_type == 'video':
            thumbnail_url = self._generate_video_thumbnail(
                item_id=collection_item.id,
                video=downloaded,
            )

        metadata: JsonObject = {
            'thumbnailUrl': thumbnail_url,
            'format': self._format_from_content_type(content_type),
            'sizeBytes': stored_object.size_bytes,
            'width': 0,
            'height': 0,
        }

        updated_item = self._collection_item_repository.mark_generated_item_ready(
            item_id=collection_item.id,
            url=stored_object.url,
            metadata=metadata,
            storage_provider=stored_object.provider,
            storage_bucket=stored_object.bucket,
            storage_key=stored_object.key,
            mime_type=stored_object.mime_type,
            size_bytes=stored_object.size_bytes,
        )
        if updated_item is None:
            raise GenerationFinalizationError('Collection item was not found while finalizing')

        self._generation_run_repository.mark_output_ready(
            output_id=output_id,
            provider_output_json=output,
            stored_output_json={
                'storedUrl': stored_object.url,
                'storageProvider': stored_object.provider,
                'storageBucket': stored_object.bucket,
                'storageKey': stored_object.key,
                'mimeType': stored_object.mime_type,
                'sizeBytes': stored_object.size_bytes,
                'thumbnailUrl': thumbnail_url,
                'mediaType': media_type,
            },
        )

    def finalize_output_failure(
        self,
        *,
        output_id: UUID,
        error_code: str,
        error_message: str,
        provider_output_json: dict[str, object] | None = None,
    ) -> None:
        collection_item = self._collection_item_repository.get_item_by_generation_run_output_id(
            output_id
        )
        if collection_item is None:
            raise GenerationFinalizationError(
                f'Collection item linked to output {output_id} was not found while marking failure'
            )

        updated_item = self._collection_item_repository.mark_generated_item_failed(
            item_id=collection_item.id, error_message=error_message
        )
        if updated_item is None:
            raise GenerationFinalizationError('Collection item was not found while marking failure')

        self._generation_run_repository.mark_output_failed(
            output_id=output_id,
            error_code=error_code,
            error_message=error_message,
            provider_output_json=provider_output_json,
        )

    def _build_storage_key(self, *, item_id: UUID, content_type: str) -> str:
        extension = self._format_from_content_type(content_type)
        return f'generated/{item_id}.{extension}'

    def _format_from_content_type(self, content_type: str) -> str:
        if '/' not in content_type:
            return 'png'
        suffix = content_type.split('/', maxsplit=1)[1]
        suffix = suffix.split(';', maxsplit=1)[0].strip().lower()
        if len(suffix) == 0:
            return 'png'

        if suffix == 'jpeg':
            return 'jpg'

        safe_suffix = ''.join(char for char in suffix if char.isalnum())
        if len(safe_suffix) == 0:
            return 'png'

        return safe_suffix

    def _resolve_media_type(self, *, output: dict[str, object], content_type: str) -> str:
        raw_media_type = output.get('media_type')
        if isinstance(raw_media_type, str) and raw_media_type in {'image', 'video'}:
            return raw_media_type
        return 'video' if content_type.startswith('video/') else 'image'

    def _generate_video_thumbnail(self, *, item_id: UUID, video: bytes) -> str:
        try:
            thumbnail = self._video_thumbnail_generator.extract_first_frame(
                video_stream=BytesIO(video)
            )
        except VideoThumbnailGenerationError:
            return ''

        try:
            stored_thumbnail = self._object_storage.upload_object(
                key=f'generated/{item_id}-thumb.jpg',
                content_type='image/jpeg',
                body=BytesIO(thumbnail),
                size_bytes=len(thumbnail),
            )
        except StorageError:
            return ''

        return stored_thumbnail.url
