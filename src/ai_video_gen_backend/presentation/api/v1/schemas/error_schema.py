from __future__ import annotations

from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class ErrorPayload(StrictSchema):
    code: str
    message: str
    details: dict[str, object] | None = None


class ErrorEnvelope(StrictSchema):
    error: ErrorPayload
