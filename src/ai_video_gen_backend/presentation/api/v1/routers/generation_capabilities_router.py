from __future__ import annotations

from fastapi import APIRouter, Depends

from ai_video_gen_backend.application.generation import GetGenerationCapabilitiesUseCase
from ai_video_gen_backend.domain.generation import GenerationCapabilityRegistryPort
from ai_video_gen_backend.infrastructure.providers.fal import CapabilityRegistryLoadError
from ai_video_gen_backend.presentation.api.dependencies import get_generation_capability_registry
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import GenerationCapabilitiesResponse

router = APIRouter(tags=['generation'])


@router.get('/generation/capabilities', response_model=GenerationCapabilitiesResponse)
def get_generation_capabilities(
    capability_registry: GenerationCapabilityRegistryPort = Depends(
        get_generation_capability_registry
    ),
) -> GenerationCapabilitiesResponse:
    use_case = GetGenerationCapabilitiesUseCase(capability_registry)
    try:
        capabilities = use_case.execute()
    except CapabilityRegistryLoadError as exc:
        raise ApiError(
            status_code=500,
            code='capability_registry_load_failed',
            message='Failed to load generation capabilities',
        ) from exc

    return GenerationCapabilitiesResponse.from_domain(capabilities)
