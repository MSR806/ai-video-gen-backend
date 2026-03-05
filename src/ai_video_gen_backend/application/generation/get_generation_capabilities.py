from __future__ import annotations

from ai_video_gen_backend.domain.generation import (
    GenerationCapabilities,
    GenerationCapabilityRegistryPort,
)


class GetGenerationCapabilitiesUseCase:
    def __init__(self, capability_registry: GenerationCapabilityRegistryPort) -> None:
        self._capability_registry = capability_registry

    def execute(self) -> GenerationCapabilities:
        return self._capability_registry.list_capabilities()
