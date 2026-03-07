from __future__ import annotations

from ai_video_gen_backend.domain.generation import (
    CapabilityRegistryError,
    GenerationCapabilities,
    GenerationCapabilityRegistryPort,
)


class GenerationCapabilitiesLoadError(Exception):
    """Raised when generation capabilities cannot be loaded from registry."""


class GetGenerationCapabilitiesUseCase:
    def __init__(self, capability_registry: GenerationCapabilityRegistryPort) -> None:
        self._capability_registry = capability_registry

    def execute(self) -> GenerationCapabilities:
        try:
            return self._capability_registry.list_capabilities()
        except CapabilityRegistryError as exc:
            raise GenerationCapabilitiesLoadError from exc
