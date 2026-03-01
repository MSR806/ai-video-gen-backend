from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from ai_video_gen_backend.domain.collection_item import (
    CollectionItem,
    CollectionItemCreationPayload,
    CollectionItemRepositoryPort,
    JsonObject,
    MediaType,
    ObjectStoragePort,
    StorageError,
    VideoThumbnailGenerationError,
    VideoThumbnailGeneratorPort,
)

logger = logging.getLogger(__name__)


class UnsupportedMediaTypeError(Exception):
    """Raised when uploaded file MIME type is not allowed."""


class PayloadTooLargeError(Exception):
    """Raised when uploaded file exceeds configured size limit."""


class UploadCollectionItemUseCase:
    def __init__(
        self,
        collection_item_repository: CollectionItemRepositoryPort,
        object_storage: ObjectStoragePort,
        video_thumbnail_generator: VideoThumbnailGeneratorPort,
        *,
        max_upload_size_bytes: int,
        allowed_mime_prefixes: Iterable[str],
    ) -> None:
        self._collection_item_repository = collection_item_repository
        self._object_storage = object_storage
        self._video_thumbnail_generator = video_thumbnail_generator
        self._max_upload_size_bytes = max_upload_size_bytes
        self._allowed_mime_prefixes = tuple(allowed_mime_prefixes)

    def execute(
        self,
        *,
        project_id: UUID,
        collection_id: UUID,
        filename: str,
        content_type: str,
        file_stream: BinaryIO,
        size_bytes: int,
        name: str | None,
        description: str | None,
        metadata: JsonObject | None = None,
    ) -> CollectionItem:
        if size_bytes > self._max_upload_size_bytes:
            raise PayloadTooLargeError

        if not self._is_allowed_content_type(content_type):
            raise UnsupportedMediaTypeError

        media_type = self._to_media_type(content_type)
        safe_filename = self._sanitize_filename(filename)
        object_key = self._build_storage_key(
            project_id=project_id,
            collection_id=collection_id,
            filename=safe_filename,
        )

        stored_object = self._object_storage.upload_object(
            key=object_key,
            content_type=content_type,
            body=file_stream,
            size_bytes=size_bytes,
        )
        uploaded_object_keys = [stored_object.key]

        thumbnail_url = self._resolve_thumbnail_url(
            media_type=media_type,
            original_object_key=stored_object.key,
            original_object_url=stored_object.url,
            file_stream=file_stream,
            uploaded_object_keys=uploaded_object_keys,
        )

        merged_metadata = self._merge_metadata(
            metadata=metadata,
            media_type=media_type,
            thumbnail_url=thumbnail_url,
            size_bytes=size_bytes,
            content_type=content_type,
            filename=safe_filename,
        )

        payload = CollectionItemCreationPayload(
            project_id=project_id,
            collection_id=collection_id,
            media_type=media_type,
            name=(
                name.strip()
                if isinstance(name, str) and len(name.strip()) > 0
                else Path(safe_filename).stem
            ),
            description=description.strip() if isinstance(description, str) else '',
            url=stored_object.url,
            metadata=merged_metadata,
            generation_source='upload',
            storage_provider=stored_object.provider,
            storage_bucket=stored_object.bucket,
            storage_key=stored_object.key,
            mime_type=stored_object.mime_type,
            size_bytes=stored_object.size_bytes,
        )

        try:
            return self._collection_item_repository.create_item(payload)
        except Exception:
            for uploaded_key in reversed(uploaded_object_keys):
                with suppress(Exception):
                    self._object_storage.delete_object(key=uploaded_key)
            raise

    def _is_allowed_content_type(self, content_type: str) -> bool:
        return any(content_type.startswith(prefix) for prefix in self._allowed_mime_prefixes)

    def _to_media_type(self, content_type: str) -> MediaType:
        if content_type.startswith('image/'):
            return 'image'
        return 'video'

    def _sanitize_filename(self, filename: str) -> str:
        original = Path(filename).name
        stem = Path(original).stem.strip()
        suffix = Path(original).suffix

        safe_stem = re.sub(r'[^A-Za-z0-9._-]+', '-', stem).strip('-')
        if len(safe_stem) == 0:
            safe_stem = 'upload'

        return f'{safe_stem}{suffix.lower()}'

    def _build_storage_key(self, *, project_id: UUID, collection_id: UUID, filename: str) -> str:
        return f'projects/{project_id}/collections/{collection_id}/{uuid4()}-{filename}'

    def _build_thumbnail_key(self, *, original_object_key: str) -> str:
        original_path = Path(original_object_key)
        if len(original_path.suffix) > 0:
            return f'{original_object_key[: -len(original_path.suffix)]}-thumb.jpg'
        return f'{original_object_key}-thumb.jpg'

    def _resolve_thumbnail_url(
        self,
        *,
        media_type: MediaType,
        original_object_key: str,
        original_object_url: str,
        file_stream: BinaryIO,
        uploaded_object_keys: list[str],
    ) -> str:
        if media_type == 'image':
            return original_object_url

        try:
            thumbnail_bytes = self._video_thumbnail_generator.extract_first_frame(
                video_stream=file_stream
            )
            thumbnail_key = self._build_thumbnail_key(original_object_key=original_object_key)
            thumbnail_object = self._object_storage.upload_object(
                key=thumbnail_key,
                content_type='image/jpeg',
                body=BytesIO(thumbnail_bytes),
                size_bytes=len(thumbnail_bytes),
            )
            uploaded_object_keys.append(thumbnail_object.key)
            return thumbnail_object.url
        except (StorageError, VideoThumbnailGenerationError) as exc:
            logger.warning(
                'Video thumbnail generation failed for %s: %s',
                original_object_key,
                str(exc),
            )
            return ''

    def _merge_metadata(
        self,
        *,
        metadata: JsonObject | None,
        media_type: MediaType,
        thumbnail_url: str,
        size_bytes: int,
        content_type: str,
        filename: str,
    ) -> JsonObject:
        merged: JsonObject = dict(metadata) if metadata is not None else {}

        if 'format' not in merged:
            merged['format'] = self._infer_format(content_type=content_type, filename=filename)

        merged['thumbnailUrl'] = thumbnail_url

        if 'width' not in merged:
            merged['width'] = 0

        if 'height' not in merged:
            merged['height'] = 0

        if media_type == 'video' and 'duration' not in merged:
            merged['duration'] = 0

        if 'sizeBytes' not in merged:
            merged['sizeBytes'] = size_bytes

        return merged

    def _infer_format(self, *, content_type: str, filename: str) -> str:
        if '/' in content_type:
            content_format = content_type.split('/', maxsplit=1)[1].strip()
            if len(content_format) > 0:
                return content_format

        suffix = Path(filename).suffix.lower().lstrip('.')
        return suffix if len(suffix) > 0 else 'unknown'
