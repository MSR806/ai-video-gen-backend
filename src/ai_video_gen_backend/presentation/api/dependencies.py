from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.chat import SendChatMessageUseCase
from ai_video_gen_backend.application.generation import GenerationInputValidator
from ai_video_gen_backend.config.settings import Settings, get_settings
from ai_video_gen_backend.domain.chat import ChatModelPort, ChatWorkflowPort
from ai_video_gen_backend.domain.collection_item import (
    ObjectStoragePort,
    VideoThumbnailGeneratorPort,
)
from ai_video_gen_backend.domain.generation import (
    GenerationCapabilityRegistryPort,
    GenerationProviderPort,
    MediaDownloaderPort,
)
from ai_video_gen_backend.infrastructure.db.session import get_session_factory
from ai_video_gen_backend.infrastructure.providers import (
    FalGenerationProvider,
    HttpMediaDownloader,
    LangGraphChatWorkflow,
    OpenAIChatModelProvider,
)
from ai_video_gen_backend.infrastructure.providers.fal import (
    FalGenerationModelRegistry,
    ModelRegistryLoader,
)
from ai_video_gen_backend.infrastructure.repositories import ChatSqlRepository
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


@lru_cache(maxsize=1)
def _cached_generation_registry(ttl_seconds: int) -> GenerationCapabilityRegistryPort:
    loader = ModelRegistryLoader(ttl_seconds=ttl_seconds)
    return FalGenerationModelRegistry(loader)


def get_generation_capability_registry(
    settings: Settings = Depends(get_app_settings),
) -> GenerationCapabilityRegistryPort:
    return _cached_generation_registry(settings.generation_registry_cache_ttl_seconds)


def get_generation_input_validator() -> GenerationInputValidator:
    return GenerationInputValidator()


def get_media_downloader() -> MediaDownloaderPort:
    return HttpMediaDownloader()


def get_chat_model_provider(
    settings: Settings = Depends(get_app_settings),
) -> ChatModelPort:
    return OpenAIChatModelProvider(
        model_name=settings.chat_model_name,
        api_key=settings.portkey_api_key,
        base_url=settings.chat_provider_base_url,
        temperature=settings.chat_model_temperature,
    )


def get_chat_workflow(
    session: Session = Depends(get_db_session),
    chat_model_provider: ChatModelPort = Depends(get_chat_model_provider),
) -> ChatWorkflowPort:
    chat_repository = ChatSqlRepository(session)
    return LangGraphChatWorkflow(
        chat_repository=chat_repository,
        chat_model=chat_model_provider,
    )


def get_send_chat_message_use_case(
    session: Session = Depends(get_db_session),
    chat_workflow: ChatWorkflowPort = Depends(get_chat_workflow),
) -> SendChatMessageUseCase:
    chat_repository = ChatSqlRepository(session)
    return SendChatMessageUseCase(chat_repository=chat_repository, chat_workflow=chat_workflow)
