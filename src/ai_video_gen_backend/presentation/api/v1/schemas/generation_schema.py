from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.collection_item import CollectionItem
from ai_video_gen_backend.domain.generation import GenerationRun, GenerationRunOutput
from ai_video_gen_backend.domain.types import JsonValue
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class GenerationRunError(StrictSchema):
    code: str | None = None
    message: str | None = None


class GenerationRunOutputResponse(StrictSchema):
    id: UUID = Field(alias='outputId')
    output_index: int = Field(alias='outputIndex')
    status: Literal['QUEUED', 'READY', 'FAILED']
    collection_item_id: UUID | None = Field(default=None, alias='collectionItemId')
    error_code: str | None = Field(default=None, alias='errorCode')
    error_message: str | None = Field(default=None, alias='errorMessage')
    provider_output: dict[str, JsonValue] | None = Field(default=None, alias='providerOutput')
    stored_output: dict[str, JsonValue] | None = Field(default=None, alias='storedOutput')

    @classmethod
    def from_domain(
        cls,
        output: GenerationRunOutput,
        collection_item_id: UUID | None,
    ) -> GenerationRunOutputResponse:
        return cls(
            id=output.id,
            output_index=output.output_index,
            status=output.status,
            collection_item_id=collection_item_id,
            error_code=output.error_code,
            error_message=output.error_message,
            provider_output=output.provider_output_json,
            stored_output=output.stored_output_json,
        )


class GenerationRunResponse(StrictSchema):
    id: UUID = Field(alias='runId')
    status: Literal['QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'PARTIAL_FAILED', 'FAILED', 'CANCELLED']
    operation_key: str = Field(alias='operationKey')
    provider: str
    model_key: str = Field(alias='modelKey')
    endpoint_id: str | None = Field(default=None, alias='endpointId')
    project_id: UUID = Field(alias='projectId')
    requested_output_count: int = Field(alias='requestedOutputCount')
    outputs: list[GenerationRunOutputResponse] = Field(default_factory=list)
    error: GenerationRunError | None = None
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')
    submitted_at: datetime | None = Field(default=None, alias='submittedAt')
    completed_at: datetime | None = Field(default=None, alias='completedAt')

    @classmethod
    def from_domain(
        cls,
        run: GenerationRun,
        outputs: list[GenerationRunOutput],
        collection_items: list[CollectionItem],
    ) -> GenerationRunResponse:
        error: GenerationRunError | None = None
        if run.error_code is not None or run.error_message is not None:
            error = GenerationRunError(code=run.error_code, message=run.error_message)

        collection_item_id_by_output_id = {
            item.generation_run_output_id: item.id
            for item in collection_items
            if item.generation_run_output_id is not None
        }

        return cls(
            id=run.id,
            status=run.status,
            operation_key=run.operation_key,
            provider=run.provider,
            model_key=run.model_key,
            endpoint_id=run.endpoint_id,
            project_id=run.project_id,
            requested_output_count=run.requested_output_count,
            outputs=[
                GenerationRunOutputResponse.from_domain(
                    output,
                    collection_item_id=collection_item_id_by_output_id.get(output.id),
                )
                for output in outputs
            ],
            error=error,
            created_at=run.created_at,
            updated_at=run.updated_at,
            submitted_at=run.submitted_at,
            completed_at=run.completed_at,
        )
