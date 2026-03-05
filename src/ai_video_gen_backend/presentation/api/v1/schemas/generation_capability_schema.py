from __future__ import annotations

from pydantic import Field

from ai_video_gen_backend.domain.generation import (
    GenerationCapabilities,
    InputFieldCapability,
    ModelCapability,
    OperationCapability,
)
from ai_video_gen_backend.domain.types import JsonValue
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class InputFieldCapabilityResponse(StrictSchema):
    key: str
    type: str
    required: bool
    description: str | None
    default: JsonValue | None = None
    enum: list[JsonValue] | None = None
    format: str | None = None
    items_type: str | None = Field(default=None, alias='itemsType')

    @classmethod
    def from_domain(cls, field: InputFieldCapability) -> InputFieldCapabilityResponse:
        return cls(
            key=field.key,
            type=field.type,
            required=field.required,
            description=field.description,
            default=field.default,
            enum=field.enum,
            format=field.format,
            items_type=field.items_type,
        )


class OperationCapabilityResponse(StrictSchema):
    operation_key: str = Field(alias='operationKey')
    endpoint_id: str = Field(alias='endpointId')
    required: list[str]
    fields: list[InputFieldCapabilityResponse]

    @classmethod
    def from_domain(cls, operation: OperationCapability) -> OperationCapabilityResponse:
        return cls(
            operation_key=operation.operation_key,
            endpoint_id=operation.endpoint_id,
            required=operation.required,
            fields=[InputFieldCapabilityResponse.from_domain(field) for field in operation.fields],
        )


class ModelCapabilityResponse(StrictSchema):
    model: str
    model_key: str = Field(alias='modelKey')
    provider: str
    operations: list[OperationCapabilityResponse]

    @classmethod
    def from_domain(cls, model: ModelCapability) -> ModelCapabilityResponse:
        return cls(
            model=model.model,
            model_key=model.model_key,
            provider=model.provider,
            operations=[
                OperationCapabilityResponse.from_domain(operation) for operation in model.operations
            ],
        )


class GenerationCapabilitiesResponse(StrictSchema):
    image: list[ModelCapabilityResponse]
    video: list[ModelCapabilityResponse]

    @classmethod
    def from_domain(cls, capabilities: GenerationCapabilities) -> GenerationCapabilitiesResponse:
        return cls(
            image=[ModelCapabilityResponse.from_domain(model) for model in capabilities.image],
            video=[ModelCapabilityResponse.from_domain(model) for model in capabilities.video],
        )
