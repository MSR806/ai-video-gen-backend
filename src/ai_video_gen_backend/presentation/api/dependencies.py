from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from ai_video_gen_backend.config.settings import Settings, get_settings
from ai_video_gen_backend.domain.collection_item import (
    ObjectStoragePort,
    VideoThumbnailGeneratorPort,
)
from ai_video_gen_backend.domain.generation import GenerationProviderPort, MediaDownloaderPort
from ai_video_gen_backend.infrastructure.db.session import get_session_factory
from ai_video_gen_backend.infrastructure.providers import FalGenerationProvider, HttpMediaDownloader
from ai_video_gen_backend.infrastructure.storage import (
    FfmpegVideoThumbnailGenerator,
    S3ObjectStorage,
)


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_app_settings() -> Settings:
    return get_settings()


def get_object_storage(
    settings: Settings = Depends(get_app_settings),
) -> ObjectStoragePort:
    return S3ObjectStorage(
        endpoint=settings.storage_endpoint,
        public_base_url=settings.storage_public_base_url,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        bucket=settings.storage_bucket,
        region=settings.storage_region,
        secure=settings.storage_secure,
    )


def get_video_thumbnail_generator(
    settings: Settings = Depends(get_app_settings),
) -> VideoThumbnailGeneratorPort:
    return FfmpegVideoThumbnailGenerator(ffmpeg_bin=settings.video_thumbnail_ffmpeg_bin)


def get_generation_provider(
    settings: Settings = Depends(get_app_settings),
) -> GenerationProviderPort:
    return FalGenerationProvider(api_key=settings.fal_api_key)


def get_media_downloader() -> MediaDownloaderPort:
    return HttpMediaDownloader()
