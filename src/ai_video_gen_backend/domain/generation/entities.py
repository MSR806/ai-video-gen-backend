from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from ai_video_gen_backend.domain.types import JsonObject

GenerationRunStatus = Literal[
    'QUEUED',
    'IN_PROGRESS',
    'SUCCEEDED',
    'PARTIAL_FAILED',
    'FAILED',
    'CANCELLED',
]
GenerationRunOutputStatus = Literal['QUEUED', 'READY', 'FAILED']
OutputMediaType = Literal['image', 'video']


@dataclass(frozen=True, slots=True)
class GenerationRunRequest:
    project_id: UUID
    collection_id: UUID
    model_key: str
    operation_key: str
    inputs: JsonObject
    output_count: int = 1
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class GenerationRun:
    id: UUID
    project_id: UUID
    operation_key: str
    provider: str
    model_key: str
    endpoint_id: str | None
    status: GenerationRunStatus
    requested_output_count: int
    inputs_json: JsonObject
    provider_request_id: str | None
    provider_response_json: JsonObject | None
    idempotency_key: str | None
    error_code: str | None
    error_message: str | None
    submitted_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class GenerationRunOutput:
    id: UUID
    run_id: UUID
    output_index: int
    status: GenerationRunOutputStatus
    provider_output_json: JsonObject | None
    stored_output_json: JsonObject | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SubmittedRunOutput:
    output_id: UUID
    output_index: int
    status: GenerationRunOutputStatus
    collection_item_id: UUID


@dataclass(frozen=True, slots=True)
class GenerationRunSubmission:
    run: GenerationRun
    outputs: list[SubmittedRunOutput]


@dataclass(frozen=True, slots=True)
class ProviderSubmission:
    provider_request_id: str


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    status: Literal['IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED']


@dataclass(frozen=True, slots=True)
class GeneratedOutput:
    index: int
    media_type: OutputMediaType
    provider_url: str
    metadata: JsonObject


@dataclass(frozen=True, slots=True)
class ProviderResult:
    status: Literal['SUCCEEDED', 'FAILED']
    outputs: list[GeneratedOutput]
    raw_response: JsonObject
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderWebhookEvent:
    provider_request_id: str
    status: Literal['SUCCEEDED', 'FAILED']
    outputs: list[GeneratedOutput]
    raw_response: JsonObject
    error_message: str | None = None
