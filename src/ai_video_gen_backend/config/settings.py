from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = 'development'
    log_level: str = 'INFO'
    api_v1_prefix: str = '/api/v1'
    database_url: str = 'postgresql+psycopg://app:app@localhost:5432/ai_video_gen'
    storage_endpoint: str = 'http://minio:9000'
    storage_public_base_url: str = 'http://localhost:9000'
    storage_access_key: str = 'minioadmin'
    storage_secret_key: str = 'minioadmin'
    storage_bucket: str = 'ai-video-gen-media'
    storage_region: str = 'us-east-1'
    storage_secure: bool = False
    video_thumbnail_ffmpeg_bin: str = 'ffmpeg'
    max_upload_size_mb: int = 50
    allowed_upload_mime_prefixes: tuple[str, ...] = ('image/', 'video/')
    fal_api_key: str = ''
    generation_default_provider: str = 'fal'
    generation_webhook_public_base_url: str = 'http://localhost:8000'
    generation_webhook_token: str = ''
    generation_status_reconcile_after_seconds: int = 20
    generation_result_max_download_mb: int = 25

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
