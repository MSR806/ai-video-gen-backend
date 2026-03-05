from .collection_router import router as collection_router
from .generation_capabilities_router import router as generation_capabilities_router
from .generation_router import router as generation_router
from .project_router import router as project_router
from .provider_webhook_router import router as provider_webhook_router
from .scene_router import router as scene_router

__all__ = [
    'collection_router',
    'generation_capabilities_router',
    'generation_router',
    'project_router',
    'provider_webhook_router',
    'scene_router',
]
