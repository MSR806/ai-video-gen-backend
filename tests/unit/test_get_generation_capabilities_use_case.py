from __future__ import annotations

import pytest

from ai_video_gen_backend.application.generation import (
    GenerationCapabilitiesLoadError,
    GetGenerationCapabilitiesUseCase,
)
from ai_video_gen_backend.domain.generation import (
    CapabilityRegistryError,
    GenerationCapabilities,
    ResolvedGenerationOperation,
)


class FakeCapabilityRegistry:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def list_capabilities(self) -> GenerationCapabilities:
        if self.fail:
            raise CapabilityRegistryError('registry unavailable')
        return GenerationCapabilities(image=[], video=[])

    def has_model(self, *, model_key: str) -> bool:
        del model_key
        return False

    def resolve_operation(
        self, *, model_key: str, operation_key: str
    ) -> ResolvedGenerationOperation | None:
        del model_key, operation_key
        return None


def test_get_generation_capabilities_success() -> None:
    use_case = GetGenerationCapabilitiesUseCase(FakeCapabilityRegistry())

    capabilities = use_case.execute()

    assert capabilities.image == []
    assert capabilities.video == []


def test_get_generation_capabilities_wraps_registry_errors() -> None:
    use_case = GetGenerationCapabilitiesUseCase(FakeCapabilityRegistry(fail=True))

    with pytest.raises(GenerationCapabilitiesLoadError):
        use_case.execute()
