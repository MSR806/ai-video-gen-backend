from __future__ import annotations

from fastapi import APIRouter, Depends

from ai_video_gen_backend.application.generation import GetGenerationCapabilitiesUseCase
from ai_video_gen_backend.domain.generation import GenerationCapabilityRegistryPort
from ai_video_gen_backend.presentation.api.dependencies import get_generation_capability_registry
from ai_video_gen_backend.presentation.api.v1.schemas import GenerationCapabilitiesResponse

router = APIRouter(tags=['generation'])


@router.get('/generation/capabilities', response_model=GenerationCapabilitiesResponse)
def get_generation_capabilities(
    capability_registry: GenerationCapabilityRegistryPort = Depends(
        get_generation_capability_registry
    ),
) -> GenerationCapabilitiesResponse:
    use_case = GetGenerationCapabilitiesUseCase(capability_registry)
    capabilities = use_case.execute()
    return GenerationCapabilitiesResponse.from_domain(capabilities)
