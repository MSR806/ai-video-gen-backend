from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.chat import SendChatMessageUseCase
from ai_video_gen_backend.application.generation import (
    GenerationInputValidator,
    SubmitGenerationRunUseCase,
)
from ai_video_gen_backend.application.shot import (
    CraftShotImagePromptUseCase,
    EnsureShotVisualCollectionUseCase,
    GenerateShotsUseCase,
    GenerateShotVisualsUseCase,
)
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
from ai_video_gen_backend.domain.shot import ShotGenerationPort, ShotImagePromptCrafterPort
from ai_video_gen_backend.infrastructure.db.session import get_session_factory
from ai_video_gen_backend.infrastructure.providers import (
    FalGenerationProvider,
    HttpMediaDownloader,
    LangGraphChatWorkflow,
    OpenAIChatModelProvider,
    OpenAIShotGenerationProvider,
    OpenAIShotImagePromptCrafter,
)
from ai_video_gen_backend.infrastructure.providers.fal import (
    FalGenerationModelRegistry,
    ModelRegistryLoader,
)
from ai_video_gen_backend.infrastructure.providers.langgraph_postgres_checkpointer import (
    close_langgraph_postgres_checkpointer,
    get_langgraph_postgres_checkpointer,
)
from ai_video_gen_backend.infrastructure.repositories import (
    ChatSqlRepository,
    CollectionItemSqlRepository,
    CollectionSqlRepository,
    GenerationRunSqlRepository,
    ProjectSqlRepository,
    ScreenplaySqlRepository,
    ShotSqlRepository,
)
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


def get_shot_generation_provider(
    settings: Settings = Depends(get_app_settings),
) -> ShotGenerationPort:
    return OpenAIShotGenerationProvider(
        model_name=settings.chat_model_name,
        api_key=settings.portkey_api_key,
        base_url=settings.chat_provider_base_url,
        temperature=settings.chat_model_temperature,
    )


def get_shot_image_prompt_crafter(
    settings: Settings = Depends(get_app_settings),
) -> ShotImagePromptCrafterPort:
    return OpenAIShotImagePromptCrafter(
        model_name=settings.chat_model_name,
        api_key=settings.portkey_api_key,
        base_url=settings.chat_provider_base_url,
        temperature=settings.chat_model_temperature,
    )


def get_craft_shot_image_prompt_use_case(
    session: Session = Depends(get_db_session),
    prompt_crafter: ShotImagePromptCrafterPort = Depends(get_shot_image_prompt_crafter),
) -> CraftShotImagePromptUseCase:
    return CraftShotImagePromptUseCase(
        project_repository=ProjectSqlRepository(session),
        screenplay_repository=ScreenplaySqlRepository(session),
        shot_repository=ShotSqlRepository(session),
        prompt_crafter=prompt_crafter,
    )


def get_generate_shots_use_case(
    session: Session = Depends(get_db_session),
    shot_generator: ShotGenerationPort = Depends(get_shot_generation_provider),
) -> GenerateShotsUseCase:
    return GenerateShotsUseCase(
        shot_repository=ShotSqlRepository(session),
        screenplay_repository=ScreenplaySqlRepository(session),
        shot_generator=shot_generator,
    )


def get_ensure_shot_visual_collection_use_case(
    session: Session = Depends(get_db_session),
) -> EnsureShotVisualCollectionUseCase:
    return EnsureShotVisualCollectionUseCase(
        shot_repository=ShotSqlRepository(session),
        screenplay_repository=ScreenplaySqlRepository(session),
        collection_repository=CollectionSqlRepository(session),
    )


def get_submit_generation_run_use_case(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    generation_provider: GenerationProviderPort = Depends(get_generation_provider),
    capability_registry: GenerationCapabilityRegistryPort = Depends(
        get_generation_capability_registry
    ),
    input_validator: GenerationInputValidator = Depends(get_generation_input_validator),
) -> SubmitGenerationRunUseCase:
    base = settings.generation_webhook_public_base_url.rstrip('/')
    prefix = settings.api_v1_prefix
    if not prefix.startswith('/'):
        prefix = f'/{prefix}'
    webhook_url = f'{base}{prefix}/provider-webhooks/fal?token={settings.generation_webhook_token}'
    return SubmitGenerationRunUseCase(
        collection_item_repository=CollectionItemSqlRepository(session),
        generation_run_repository=GenerationRunSqlRepository(session),
        generation_provider=generation_provider,
        capability_registry=capability_registry,
        input_validator=input_validator,
        webhook_url=webhook_url,
    )


def get_generate_shot_visuals_use_case(
    session: Session = Depends(get_db_session),
    ensure_shot_visual_collection_use_case: EnsureShotVisualCollectionUseCase = Depends(
        get_ensure_shot_visual_collection_use_case
    ),
    craft_shot_image_prompt_use_case: CraftShotImagePromptUseCase = Depends(
        get_craft_shot_image_prompt_use_case
    ),
    submit_generation_run_use_case: SubmitGenerationRunUseCase = Depends(
        get_submit_generation_run_use_case
    ),
) -> GenerateShotVisualsUseCase:
    return GenerateShotVisualsUseCase(
        project_repository=ProjectSqlRepository(session),
        screenplay_repository=ScreenplaySqlRepository(session),
        shot_repository=ShotSqlRepository(session),
        ensure_shot_visual_collection=ensure_shot_visual_collection_use_case,
        craft_shot_image_prompt=craft_shot_image_prompt_use_case,
        submit_generation_run=submit_generation_run_use_case,
    )


async def get_screenplay_langgraph_checkpointer(
    settings: Settings = Depends(get_app_settings),
) -> object:
    return await get_langgraph_postgres_checkpointer(database_url=settings.database_url)


def get_chat_workflow(
    session: Session = Depends(get_db_session),
    chat_model_provider: ChatModelPort = Depends(get_chat_model_provider),
) -> ChatWorkflowPort:
    chat_repository = ChatSqlRepository(session)
    return LangGraphChatWorkflow(
        chat_repository=chat_repository,
        chat_model=chat_model_provider,
        screenplay_repository=ScreenplaySqlRepository(session),
    )


def get_send_chat_message_use_case(
    session: Session = Depends(get_db_session),
    chat_workflow: ChatWorkflowPort = Depends(get_chat_workflow),
) -> SendChatMessageUseCase:
    chat_repository = ChatSqlRepository(session)
    return SendChatMessageUseCase(chat_repository=chat_repository, chat_workflow=chat_workflow)


async def shutdown_screenplay_langgraph_checkpointer() -> None:
    await close_langgraph_postgres_checkpointer()
