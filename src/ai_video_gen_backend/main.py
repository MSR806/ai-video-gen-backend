from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_video_gen_backend.config.logging import configure_logging
from ai_video_gen_backend.config.settings import Settings, get_settings
from ai_video_gen_backend.infrastructure.db.session import configure_engine
from ai_video_gen_backend.presentation.api import api_v1_router, health_router
from ai_video_gen_backend.presentation.api.dependencies import (
    shutdown_screenplay_langgraph_checkpointer,
)
from ai_video_gen_backend.presentation.api.errors import register_exception_handlers


@asynccontextmanager
async def _app_lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        # Close persistent LangGraph Postgres checkpointer connections on shutdown.
        await shutdown_screenplay_langgraph_checkpointer()


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    configure_logging(app_settings.log_level)
    configure_engine(app_settings.database_url, force=True)

    app = FastAPI(title='AI Video Gen Backend', version='0.1.0', lifespan=_app_lifespan)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=app_settings.api_v1_prefix)

    return app


app = create_app()
