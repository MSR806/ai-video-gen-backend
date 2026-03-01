from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = 'development'
    log_level: str = 'INFO'
    api_v1_prefix: str = '/api/v1'
    database_url: str = 'postgresql+psycopg://app:app@localhost:5432/ai_video_gen'

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
