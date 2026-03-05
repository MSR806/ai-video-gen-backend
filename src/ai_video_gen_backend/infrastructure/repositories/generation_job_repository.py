from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.generation import GenerationJob, GenerationStatus
from ai_video_gen_backend.infrastructure.db.models import GenerationJobModel


class GenerationJobSqlRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_job(
        self,
        *,
        project_id: UUID,
        collection_id: UUID,
        collection_item_id: UUID,
        operation_key: str,
        provider: str,
        model_key: str,
        endpoint_id: str,
        inputs_json: dict[str, object],
        idempotency_key: str | None,
    ) -> GenerationJob:
        model = GenerationJobModel(
            project_id=project_id,
            collection_id=collection_id,
            collection_item_id=collection_item_id,
            operation_key=operation_key,
            provider=provider,
            model_key=model_key,
            endpoint_id=endpoint_id,
            status='QUEUED',
            inputs_json=inputs_json,
            outputs_json=[],
            idempotency_key=idempotency_key,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, job_id: UUID) -> GenerationJob | None:
        model = self._session.get(GenerationJobModel, job_id)
        return self._to_domain(model) if model is not None else None

    def get_by_provider_request_id(self, provider_request_id: str) -> GenerationJob | None:
        stmt = select(GenerationJobModel).where(
            GenerationJobModel.provider_request_id == provider_request_id
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    def get_by_idempotency_key(
        self,
        *,
        project_id: UUID,
        collection_id: UUID,
        idempotency_key: str,
    ) -> GenerationJob | None:
        stmt = select(GenerationJobModel).where(
            GenerationJobModel.project_id == project_id,
            GenerationJobModel.collection_id == collection_id,
            GenerationJobModel.idempotency_key == idempotency_key,
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    def mark_submitted(self, job_id: UUID, *, provider_request_id: str) -> GenerationJob:
        model = self._require_model(job_id)
        model.provider_request_id = provider_request_id
        model.submitted_at = datetime.now(UTC)
        model.status = 'IN_PROGRESS'
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def mark_in_progress(self, job_id: UUID) -> GenerationJob:
        model = self._require_model(job_id)
        model.status = 'IN_PROGRESS'
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def mark_succeeded(
        self,
        job_id: UUID,
        *,
        provider_response_json: dict[str, object],
        outputs_json: list[dict[str, object]],
    ) -> GenerationJob:
        model = self._require_model(job_id)
        model.status = 'SUCCEEDED'
        model.provider_response_json = provider_response_json
        model.outputs_json = outputs_json
        model.error_code = None
        model.error_message = None
        model.completed_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def mark_failed(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationJob:
        model = self._require_model(job_id)
        model.status = 'FAILED'
        model.error_code = error_code
        model.error_message = error_message
        if provider_response_json is not None:
            model.provider_response_json = provider_response_json
        model.completed_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def _require_model(self, job_id: UUID) -> GenerationJobModel:
        model = self._session.get(GenerationJobModel, job_id)
        if model is None:
            msg = f'Generation job {job_id} not found'
            raise LookupError(msg)
        return model

    def _to_domain(self, model: GenerationJobModel) -> GenerationJob:
        provider_response_json = (
            dict(model.provider_response_json) if model.provider_response_json is not None else None
        )
        outputs_json = [dict(output) for output in model.outputs_json]
        return GenerationJob(
            id=model.id,
            project_id=model.project_id,
            collection_id=model.collection_id,
            collection_item_id=model.collection_item_id,
            operation_key=model.operation_key,
            provider=model.provider,
            model_key=model.model_key,
            endpoint_id=model.endpoint_id,
            status=cast(GenerationStatus, model.status),
            inputs_json=dict(model.inputs_json),
            outputs_json=outputs_json,
            provider_request_id=model.provider_request_id,
            provider_response_json=provider_response_json,
            idempotency_key=model.idempotency_key,
            error_code=model.error_code,
            error_message=model.error_message,
            submitted_at=model.submitted_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
