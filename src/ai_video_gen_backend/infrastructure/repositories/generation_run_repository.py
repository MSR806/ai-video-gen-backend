from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.generation import (
    GenerationRun,
    GenerationRunOutput,
    GenerationRunOutputStatus,
    GenerationRunStatus,
)
from ai_video_gen_backend.infrastructure.db.models import (
    GenerationRunModel,
    GenerationRunOutputModel,
)


class GenerationRunSqlRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(
        self,
        *,
        project_id: UUID,
        operation_key: str,
        provider: str,
        model_key: str,
        endpoint_id: str,
        requested_output_count: int,
        inputs_json: dict[str, object],
        idempotency_key: str | None,
    ) -> GenerationRun:
        model = GenerationRunModel(
            project_id=project_id,
            operation_key=operation_key,
            provider=provider,
            model_key=model_key,
            endpoint_id=endpoint_id,
            status='QUEUED',
            requested_output_count=requested_output_count,
            inputs_json=inputs_json,
            idempotency_key=idempotency_key,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_run_domain(model)

    def create_run_outputs(self, *, run_id: UUID, output_count: int) -> list[GenerationRunOutput]:
        models = [
            GenerationRunOutputModel(
                run_id=run_id,
                output_index=index,
                status='QUEUED',
                provider_output_json=None,
                stored_output_json=None,
                error_code=None,
                error_message=None,
            )
            for index in range(output_count)
        ]
        self._session.add_all(models)
        self._session.commit()
        for model in models:
            self._session.refresh(model)
        return [self._to_output_domain(model) for model in models]

    def get_run_by_id(self, run_id: UUID) -> GenerationRun | None:
        model = self._session.get(GenerationRunModel, run_id)
        return self._to_run_domain(model) if model is not None else None

    def get_run_by_provider_request_id(self, provider_request_id: str) -> GenerationRun | None:
        stmt = select(GenerationRunModel).where(
            GenerationRunModel.provider_request_id == provider_request_id
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return self._to_run_domain(model) if model is not None else None

    def get_run_by_idempotency_key(
        self,
        *,
        project_id: UUID,
        idempotency_key: str,
    ) -> GenerationRun | None:
        stmt = select(GenerationRunModel).where(
            GenerationRunModel.project_id == project_id,
            GenerationRunModel.idempotency_key == idempotency_key,
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return self._to_run_domain(model) if model is not None else None

    def list_outputs_by_run_id(self, run_id: UUID) -> list[GenerationRunOutput]:
        stmt = (
            select(GenerationRunOutputModel)
            .where(GenerationRunOutputModel.run_id == run_id)
            .order_by(GenerationRunOutputModel.output_index.asc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [self._to_output_domain(model) for model in models]

    def mark_run_submitted(self, run_id: UUID, *, provider_request_id: str) -> GenerationRun:
        model = self._require_run_model(run_id)
        model.provider_request_id = provider_request_id
        model.submitted_at = datetime.now(UTC)
        model.status = 'IN_PROGRESS'
        self._session.commit()
        self._session.refresh(model)
        return self._to_run_domain(model)

    def mark_run_in_progress(self, run_id: UUID) -> GenerationRun:
        model = self._require_run_model(run_id)
        model.status = 'IN_PROGRESS'
        self._session.commit()
        self._session.refresh(model)
        return self._to_run_domain(model)

    def mark_run_succeeded(
        self,
        run_id: UUID,
        *,
        provider_response_json: dict[str, object],
    ) -> GenerationRun:
        model = self._require_run_model(run_id)
        model.status = 'SUCCEEDED'
        model.provider_response_json = provider_response_json
        model.error_code = None
        model.error_message = None
        model.completed_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(model)
        return self._to_run_domain(model)

    def mark_run_partial_failed(
        self,
        run_id: UUID,
        *,
        provider_response_json: dict[str, object],
        error_message: str,
    ) -> GenerationRun:
        model = self._require_run_model(run_id)
        model.status = 'PARTIAL_FAILED'
        model.provider_response_json = provider_response_json
        model.error_code = 'partial_failed'
        model.error_message = error_message
        model.completed_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(model)
        return self._to_run_domain(model)

    def mark_run_failed(
        self,
        run_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun:
        model = self._require_run_model(run_id)
        model.status = 'FAILED'
        model.error_code = error_code
        model.error_message = error_message
        if provider_response_json is not None:
            model.provider_response_json = provider_response_json
        model.completed_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(model)
        return self._to_run_domain(model)

    def mark_run_cancelled(
        self,
        run_id: UUID,
        *,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun:
        model = self._require_run_model(run_id)
        model.status = 'CANCELLED'
        model.error_code = 'cancelled'
        model.error_message = error_message
        if provider_response_json is not None:
            model.provider_response_json = provider_response_json
        model.completed_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(model)
        return self._to_run_domain(model)

    def mark_output_ready(
        self,
        *,
        output_id: UUID,
        provider_output_json: dict[str, object],
        stored_output_json: dict[str, object],
    ) -> GenerationRunOutput:
        model = self._require_output_model(output_id)
        model.status = 'READY'
        model.provider_output_json = provider_output_json
        model.stored_output_json = stored_output_json
        model.error_code = None
        model.error_message = None
        self._session.commit()
        self._session.refresh(model)
        return self._to_output_domain(model)

    def mark_output_failed(
        self,
        *,
        output_id: UUID,
        error_code: str,
        error_message: str,
        provider_output_json: dict[str, object] | None = None,
    ) -> GenerationRunOutput:
        model = self._require_output_model(output_id)
        model.status = 'FAILED'
        model.error_code = error_code
        model.error_message = error_message
        if provider_output_json is not None:
            model.provider_output_json = provider_output_json
        self._session.commit()
        self._session.refresh(model)
        return self._to_output_domain(model)

    def _require_run_model(self, run_id: UUID) -> GenerationRunModel:
        model = self._session.get(GenerationRunModel, run_id)
        if model is None:
            msg = f'Generation run {run_id} not found'
            raise LookupError(msg)
        return model

    def _require_output_model(self, output_id: UUID) -> GenerationRunOutputModel:
        model = self._session.get(GenerationRunOutputModel, output_id)
        if model is None:
            msg = f'Generation run output {output_id} not found'
            raise LookupError(msg)
        return model

    def _to_run_domain(self, model: GenerationRunModel) -> GenerationRun:
        provider_response_json = (
            dict(model.provider_response_json) if model.provider_response_json is not None else None
        )
        return GenerationRun(
            id=model.id,
            project_id=model.project_id,
            operation_key=model.operation_key,
            provider=model.provider,
            model_key=model.model_key,
            endpoint_id=model.endpoint_id,
            status=cast(GenerationRunStatus, model.status),
            requested_output_count=model.requested_output_count,
            inputs_json=dict(model.inputs_json),
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

    def _to_output_domain(self, model: GenerationRunOutputModel) -> GenerationRunOutput:
        provider_output_json = (
            dict(model.provider_output_json) if model.provider_output_json is not None else None
        )
        stored_output_json = (
            dict(model.stored_output_json) if model.stored_output_json is not None else None
        )
        return GenerationRunOutput(
            id=model.id,
            run_id=model.run_id,
            output_index=model.output_index,
            status=cast(GenerationRunOutputStatus, model.status),
            provider_output_json=provider_output_json,
            stored_output_json=stored_output_json,
            error_code=model.error_code,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
