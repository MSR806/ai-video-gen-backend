from __future__ import annotations

from fastapi import APIRouter

from ai_video_gen_backend.presentation.api.v1.routers import (
    chat_router,
    collection_router,
    generation_capabilities_router,
    generation_router,
    project_router,
    provider_webhook_router,
    screenplay_router,
    shot_router,
)

api_v1_router = APIRouter()
api_v1_router.include_router(chat_router)
api_v1_router.include_router(project_router)
api_v1_router.include_router(collection_router)
api_v1_router.include_router(screenplay_router)
api_v1_router.include_router(shot_router)
api_v1_router.include_router(generation_capabilities_router)
api_v1_router.include_router(generation_router)
api_v1_router.include_router(provider_webhook_router)
