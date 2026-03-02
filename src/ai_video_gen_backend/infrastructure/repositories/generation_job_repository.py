from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.generation import (
    GenerationJob,
    GenerationOperation,
    GenerationStatus,
)
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
        operation: str,
        provider: str,
        model_key: str,
        request_payload: dict[str, object],
    ) -> GenerationJob:
        model = GenerationJobModel(
            project_id=project_id,
            collection_id=collection_id,
            collection_item_id=collection_item_id,
            operation=operation,
            provider=provider,
            model_key=model_key,
            status='QUEUED',
            request_payload=request_payload,
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

    def list_jobs(
        self,
        *,
        collection_id: UUID | None = None,
        project_id: UUID | None = None,
        statuses: list[GenerationStatus] | None = None,
        limit: int = 50,
    ) -> list[GenerationJob]:
        stmt = select(GenerationJobModel)

        if collection_id is not None:
            stmt = stmt.where(GenerationJobModel.collection_id == collection_id)
        if project_id is not None:
            stmt = stmt.where(GenerationJobModel.project_id == project_id)
        if statuses:
            stmt = stmt.where(GenerationJobModel.status.in_(statuses))

        stmt = stmt.order_by(GenerationJobModel.created_at.desc()).limit(limit)
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(model) for model in models]

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
        provider_response: dict[str, object],
    ) -> GenerationJob:
        model = self._require_model(job_id)
        model.status = 'SUCCEEDED'
        model.provider_response = provider_response
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
        provider_response: dict[str, object] | None = None,
    ) -> GenerationJob:
        model = self._require_model(job_id)
        model.status = 'FAILED'
        model.error_code = error_code
        model.error_message = error_message
        if provider_response is not None:
            model.provider_response = provider_response
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
        provider_response = (
            dict(model.provider_response) if model.provider_response is not None else None
        )
        return GenerationJob(
            id=model.id,
            project_id=model.project_id,
            collection_id=model.collection_id,
            collection_item_id=model.collection_item_id,
            operation=cast(GenerationOperation, model.operation),
            provider=model.provider,
            model_key=model.model_key,
            status=cast(GenerationStatus, model.status),
            request_payload=dict(model.request_payload),
            provider_request_id=model.provider_request_id,
            provider_response=provider_response,
            error_code=model.error_code,
            error_message=model.error_message,
            submitted_at=model.submitted_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
