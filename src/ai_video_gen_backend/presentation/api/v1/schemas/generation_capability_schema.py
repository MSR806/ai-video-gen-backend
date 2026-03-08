from __future__ import annotations

from pydantic import Field

from ai_video_gen_backend.domain.generation import (
    GenerationCapabilities,
    InputFieldCapability,
    MediaGroupCapability,
    ModelCapability,
    OperationCapability,
)
from ai_video_gen_backend.domain.types import JsonValue
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class InputFieldCapabilityResponse(StrictSchema):
    key: str
    type: str
    required: bool
    ui_group: str | None = Field(default=None, alias='uiGroup')
    title: str | None = None
    description: str | None
    default: JsonValue | None = None
    enum: list[JsonValue] | None = None
    format: str | None = None
    items_type: str | None = Field(default=None, alias='itemsType')
    minimum: JsonValue | None = None
    maximum: JsonValue | None = None
    media_group: str | None = Field(default=None, alias='mediaGroup')
    media_order: int | None = Field(default=None, alias='mediaOrder')
    media_name: str | None = Field(default=None, alias='mediaName')

    @classmethod
    def from_domain(cls, field: InputFieldCapability) -> InputFieldCapabilityResponse:
        return cls(
            key=field.key,
            type=field.type,
            required=field.required,
            ui_group=field.ui_group,
            title=field.title,
            description=field.description,
            default=field.default,
            enum=field.enum,
            format=field.format,
            items_type=field.items_type,
            minimum=field.minimum,
            maximum=field.maximum,
            media_group=field.media_group,
            media_order=field.media_order,
            media_name=field.media_name,
        )


class MediaGroupCapabilityResponse(StrictSchema):
    group_key: str = Field(alias='groupKey')
    layout: str
    placement: str

    @classmethod
    def from_domain(cls, group: MediaGroupCapability) -> MediaGroupCapabilityResponse:
        return cls(
            group_key=group.group_key,
            layout=group.layout,
            placement=group.placement,
        )


class OperationCapabilityResponse(StrictSchema):
    operation_key: str = Field(alias='operationKey')
    operation_type: str = Field(alias='operationType')
    operation_name: str = Field(alias='operationName')
    endpoint_id: str = Field(alias='endpointId')
    required: list[str]
    fields: list[InputFieldCapabilityResponse]
    media_groups: list[MediaGroupCapabilityResponse] = Field(alias='mediaGroups')

    @classmethod
    def from_domain(cls, operation: OperationCapability) -> OperationCapabilityResponse:
        return cls(
            operation_key=operation.operation_key,
            operation_type=operation.operation_type,
            operation_name=operation.operation_name,
            endpoint_id=operation.endpoint_id,
            required=operation.required,
            fields=[InputFieldCapabilityResponse.from_domain(field) for field in operation.fields],
            media_groups=[
                MediaGroupCapabilityResponse.from_domain(group) for group in operation.media_groups
            ],
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
