from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_video_gen_backend.config.settings import Settings
from ai_video_gen_backend.infrastructure.db.base import Base
from ai_video_gen_backend.infrastructure.db.session import (
    configure_engine,
    get_engine,
    get_session_factory,
)
from ai_video_gen_backend.main import create_app
from ai_video_gen_backend.presentation.api.dependencies import (
    get_screenplay_langgraph_checkpointer,
)


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    db_path = tmp_path / 'test.db'
    return Settings(
        app_env='test',
        log_level='INFO',
        api_v1_prefix='/api/v1',
        database_url=f'sqlite+pysqlite:///{db_path}',
    )


@pytest.fixture
def initialized_engine(test_settings: Settings) -> Engine:
    configure_engine(test_settings.database_url, force=True)
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def app(test_settings: Settings, initialized_engine: Engine) -> FastAPI:
    del initialized_engine
    fastapi_app = create_app(test_settings)
    fastapi_app.dependency_overrides[get_screenplay_langgraph_checkpointer] = lambda: object()
    return fastapi_app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session(initialized_engine: Engine) -> Generator[Session, None, None]:
    del initialized_engine
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
