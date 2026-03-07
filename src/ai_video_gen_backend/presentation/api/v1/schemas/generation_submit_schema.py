from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.generation import GenerationRunSubmission
from ai_video_gen_backend.domain.types import JsonValue
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class GenerationRunSubmitRequest(StrictSchema):
    project_id: UUID = Field(alias='projectId')
    model_key: str = Field(alias='modelKey')
    operation_key: str = Field(alias='operationKey')
    inputs: dict[str, JsonValue]
    output_count: int = Field(default=1, alias='outputCount')
    idempotency_key: str | None = Field(default=None, alias='idempotencyKey')


class GenerationRunSubmitOutputResponse(StrictSchema):
    output_id: UUID = Field(alias='outputId')
    output_index: int = Field(alias='outputIndex')
    status: Literal['QUEUED', 'READY', 'FAILED']
    collection_item_id: UUID = Field(alias='collectionItemId')


class GenerationRunSubmitResponse(StrictSchema):
    run_id: UUID = Field(alias='runId')
    status: Literal['QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'PARTIAL_FAILED', 'FAILED', 'CANCELLED']
    model_key: str = Field(alias='modelKey')
    operation_key: str = Field(alias='operationKey')
    outputs: list[GenerationRunSubmitOutputResponse] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, submission: GenerationRunSubmission) -> GenerationRunSubmitResponse:
        return cls(
            run_id=submission.run.id,
            status=submission.run.status,
            model_key=submission.run.model_key,
            operation_key=submission.run.operation_key,
            outputs=[
                GenerationRunSubmitOutputResponse(
                    output_id=output.output_id,
                    output_index=output.output_index,
                    status=output.status,
                    collection_item_id=output.collection_item_id,
                )
                for output in submission.outputs
            ],
        )
