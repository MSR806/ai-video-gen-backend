from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from ai_video_gen_backend.application.generation.get_generation_run import GetGenerationRunUseCase
from ai_video_gen_backend.application.generation.reconcile_generation_run import (
    ReconcileGenerationRunUseCase,
)
from ai_video_gen_backend.domain.generation import (
    GenerationRun,
    GenerationRunOutput,
    GenerationRunRepositoryPort,
    GenerationRunStatus,
)


class FakeGenerationRunRepository(GenerationRunRepositoryPort):
    def __init__(self, run: GenerationRun | None) -> None:
        self._run = run

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
        raise NotImplementedError

    def create_run_outputs(self, *, run_id: UUID, output_count: int) -> list[GenerationRunOutput]:
        raise NotImplementedError

    def get_run_by_id(self, run_id: UUID) -> GenerationRun | None:
        return self._run if self._run is not None and self._run.id == run_id else None

    def get_run_by_provider_request_id(self, provider_request_id: str) -> GenerationRun | None:
        raise NotImplementedError

    def get_run_by_idempotency_key(
        self,
        *,
        project_id: UUID,
        idempotency_key: str,
    ) -> GenerationRun | None:
        raise NotImplementedError

    def list_outputs_by_run_id(self, run_id: UUID) -> list[GenerationRunOutput]:
        raise NotImplementedError

    def mark_run_submitted(self, run_id: UUID, *, provider_request_id: str) -> GenerationRun:
        raise NotImplementedError

    def mark_run_in_progress(self, run_id: UUID) -> GenerationRun:
        raise NotImplementedError

    def mark_run_succeeded(
        self,
        run_id: UUID,
        *,
        provider_response_json: dict[str, object],
    ) -> GenerationRun:
        raise NotImplementedError

    def mark_run_partial_failed(
        self,
        run_id: UUID,
        *,
        provider_response_json: dict[str, object],
        error_message: str,
    ) -> GenerationRun:
        raise NotImplementedError

    def mark_run_failed(
        self,
        run_id: UUID,
        *,
        error_code: str,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun:
        raise NotImplementedError

    def mark_run_cancelled(
        self,
        run_id: UUID,
        *,
        error_message: str,
        provider_response_json: dict[str, object] | None = None,
    ) -> GenerationRun:
        raise NotImplementedError

    def mark_output_ready(
        self,
        *,
        output_id: UUID,
        provider_output_json: dict[str, object],
        stored_output_json: dict[str, object],
    ) -> GenerationRunOutput:
        raise NotImplementedError

    def mark_output_failed(
        self,
        *,
        output_id: UUID,
        error_code: str,
        error_message: str,
        provider_output_json: dict[str, object] | None = None,
    ) -> GenerationRunOutput:
        raise NotImplementedError


class FakeReconcileGenerationRunUseCase:
    def __init__(self) -> None:
        self.called_with: list[GenerationRun] = []

    def execute(self, run: GenerationRun) -> GenerationRun:
        self.called_with.append(run)
        return replace(run, status='IN_PROGRESS')


def _build_run(
    *, status: GenerationRunStatus = 'QUEUED', updated_at: datetime | None = None
) -> GenerationRun:
    now = updated_at or datetime.now(UTC)
    return GenerationRun(
        id=uuid4(),
        project_id=uuid4(),
        operation_key='text-to-image',
        provider='fal',
        model_key='fal/test-model',
        endpoint_id='fal/test-endpoint',
        status=status,
        requested_output_count=1,
        inputs_json={'prompt': 'storm cat'},
        provider_request_id='req-123',
        provider_response_json=None,
        idempotency_key=None,
        error_code=None,
        error_message=None,
        submitted_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


def test_returns_none_when_run_missing() -> None:
    reconcile = FakeReconcileGenerationRunUseCase()
    use_case = GetGenerationRunUseCase(
        generation_run_repository=FakeGenerationRunRepository(run=None),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
        reconcile_after_seconds=60,
    )

    assert use_case.execute(uuid4()) is None
    assert reconcile.called_with == []


def test_returns_terminal_run_without_reconciliation() -> None:
    run = _build_run(status='SUCCEEDED')
    reconcile = FakeReconcileGenerationRunUseCase()
    use_case = GetGenerationRunUseCase(
        generation_run_repository=FakeGenerationRunRepository(run=run),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
        reconcile_after_seconds=60,
    )

    assert use_case.execute(run.id) == run
    assert reconcile.called_with == []


def test_returns_run_when_provider_identifiers_are_missing() -> None:
    run = replace(_build_run(), provider_request_id=None, endpoint_id=None)
    reconcile = FakeReconcileGenerationRunUseCase()
    use_case = GetGenerationRunUseCase(
        generation_run_repository=FakeGenerationRunRepository(run=run),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
        reconcile_after_seconds=60,
    )

    assert use_case.execute(run.id) == run
    assert reconcile.called_with == []


def test_reconciles_immediately_when_threshold_is_zero() -> None:
    run = _build_run()
    reconcile = FakeReconcileGenerationRunUseCase()
    use_case = GetGenerationRunUseCase(
        generation_run_repository=FakeGenerationRunRepository(run=run),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
        reconcile_after_seconds=0,
    )

    result = use_case.execute(run.id)

    assert result is not None
    assert result.status == 'IN_PROGRESS'
    assert reconcile.called_with == [run]


def test_reconciles_when_run_age_meets_threshold() -> None:
    run = _build_run(updated_at=datetime.now(UTC) - timedelta(seconds=61))
    reconcile = FakeReconcileGenerationRunUseCase()
    use_case = GetGenerationRunUseCase(
        generation_run_repository=FakeGenerationRunRepository(run=run),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
        reconcile_after_seconds=60,
    )

    result = use_case.execute(run.id)

    assert result is not None
    assert result.status == 'IN_PROGRESS'
    assert reconcile.called_with == [run]


def test_skips_reconcile_when_run_is_fresh() -> None:
    run = _build_run(updated_at=datetime.now(UTC) - timedelta(seconds=30))
    reconcile = FakeReconcileGenerationRunUseCase()
    use_case = GetGenerationRunUseCase(
        generation_run_repository=FakeGenerationRunRepository(run=run),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
        reconcile_after_seconds=60,
    )

    assert use_case.execute(run.id) == run
    assert reconcile.called_with == []
