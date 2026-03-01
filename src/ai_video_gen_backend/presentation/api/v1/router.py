from __future__ import annotations

from fastapi import APIRouter

from ai_video_gen_backend.presentation.api.v1.routers import (
    collection_router,
    generation_router,
    project_router,
    provider_webhook_router,
    scene_router,
)

api_v1_router = APIRouter()
api_v1_router.include_router(project_router)
api_v1_router.include_router(collection_router)
api_v1_router.include_router(scene_router)
api_v1_router.include_router(generation_router)
api_v1_router.include_router(provider_webhook_router)
