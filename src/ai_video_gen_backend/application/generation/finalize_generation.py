from __future__ import annotations

from io import BytesIO
from uuid import UUID

from ai_video_gen_backend.domain.collection_item import (
    CollectionItemRepositoryPort,
    ObjectStoragePort,
    StorageError,
)
from ai_video_gen_backend.domain.generation import (
    GenerationJobRepositoryPort,
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
        generation_job_repository: GenerationJobRepositoryPort,
        object_storage: ObjectStoragePort,
        media_downloader: MediaDownloaderPort,
        max_download_bytes: int,
    ) -> None:
        self._collection_item_repository = collection_item_repository
        self._generation_job_repository = generation_job_repository
        self._object_storage = object_storage
        self._media_downloader = media_downloader
        self._max_download_bytes = max_download_bytes

    def finalize_success(
        self,
        *,
        job_id: UUID,
        item_id: UUID,
        output_url: str,
        provider_response: dict[str, object],
    ) -> None:
        try:
            downloaded, content_type = self._media_downloader.download(
                output_url, max_bytes=self._max_download_bytes
            )
        except MediaDownloadError as exc:
            raise GenerationFinalizationError(str(exc)) from exc

        storage_key = self._build_storage_key(item_id=item_id, content_type=content_type)

        try:
            stored_object = self._object_storage.upload_object(
                key=storage_key,
                content_type=content_type,
                body=BytesIO(downloaded),
                size_bytes=len(downloaded),
            )
        except StorageError as exc:
            raise GenerationFinalizationError('Failed to store generated output') from exc

        metadata: JsonObject = {
            'thumbnailUrl': stored_object.url,
            'format': self._format_from_content_type(content_type),
            'sizeBytes': stored_object.size_bytes,
            'width': 0,
            'height': 0,
        }

        updated_item = self._collection_item_repository.mark_generated_item_ready(
            item_id=item_id,
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

        self._generation_job_repository.mark_succeeded(
            job_id,
            provider_response=provider_response,
        )

    def finalize_failure(
        self,
        *,
        job_id: UUID,
        item_id: UUID,
        error_code: str,
        error_message: str,
        provider_response: dict[str, object] | None = None,
    ) -> None:
        updated_item = self._collection_item_repository.mark_generated_item_failed(
            item_id=item_id,
            error_message=error_message,
        )
        if updated_item is None:
            raise GenerationFinalizationError('Collection item was not found while marking failure')

        self._generation_job_repository.mark_failed(
            job_id,
            error_code=error_code,
            error_message=error_message,
            provider_response=provider_response,
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
