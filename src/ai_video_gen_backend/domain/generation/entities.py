from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

JsonValue = object
JsonObject = dict[str, JsonValue]

GenerationOperation = Literal['TEXT_TO_IMAGE', 'IMAGE_TO_IMAGE']
GenerationStatus = Literal['QUEUED', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED']


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    project_id: UUID
    collection_id: UUID
    operation: GenerationOperation
    prompt: str
    source_image_urls: list[str] | None = None
    model_key: str | None = None
    aspect_ratio: Literal['SQUARE', 'PORTRAIT', 'LANDSCAPE'] = 'LANDSCAPE'
    seed: int | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class GenerationJob:
    id: UUID
    project_id: UUID
    collection_id: UUID
    collection_item_id: UUID | None
    operation: GenerationOperation
    provider: str
    model_key: str
    status: GenerationStatus
    request_payload: JsonObject
    provider_request_id: str | None
    provider_response: JsonObject | None
    error_code: str | None
    error_message: str | None
    submitted_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderSubmission:
    provider_request_id: str


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    status: Literal['IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'CANCELLED']


@dataclass(frozen=True, slots=True)
class ProviderResult:
    status: Literal['SUCCEEDED', 'FAILED']
    output_url: str | None
    raw_response: JsonObject
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderWebhookEvent:
    provider_request_id: str
    status: Literal['SUCCEEDED', 'FAILED']
    output_url: str | None
    raw_response: JsonObject
    error_message: str | None = None
