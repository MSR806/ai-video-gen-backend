from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from ai_video_gen_backend.application.generation.get_generation_run import GetGenerationRunUseCase
from ai_video_gen_backend.application.generation.reconcile_generation_run import (
    ReconcileGenerationRunUseCase,
)
from ai_video_gen_backend.domain.generation import GenerationRun, GenerationRunRepositoryPort


class FakeGenerationRunRepository:
    def __init__(self, run: GenerationRun | None) -> None:
        self._run = run

    def get_run_by_id(self, run_id: UUID) -> GenerationRun | None:
        return self._run


class FakeReconcileUseCase:
    def __init__(self, result: GenerationRun) -> None:
        self.result = result
        self.calls = 0

    def execute(self, run: GenerationRun) -> GenerationRun:
        self.calls += 1
        return self.result


def _run(
    *,
    status: str = 'IN_PROGRESS',
    provider_request_id: str | None = 'req-1',
    endpoint_id: str | None = 'endpoint-1',
    updated_at: datetime | None = None,
) -> GenerationRun:
    now = updated_at or datetime.now(UTC)
    return GenerationRun(
        id=uuid4(),
        project_id=uuid4(),
        operation_key='generate',
        provider='fal',
        model_key='model-1',
        endpoint_id=endpoint_id,
        status=status,  # type: ignore[arg-type]
        requested_output_count=1,
        inputs_json={'prompt': 'hello'},
        provider_request_id=provider_request_id,
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
    reconcile = FakeReconcileUseCase(result=_run())
    use_case = GetGenerationRunUseCase(
        generation_run_repository=cast(
            GenerationRunRepositoryPort, FakeGenerationRunRepository(None)
        ),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
        reconcile_after_seconds=30,
    )

    assert use_case.execute(uuid4()) is None
    assert reconcile.calls == 0


def test_skips_reconcile_for_terminal_statuses() -> None:
    for status in ('SUCCEEDED', 'PARTIAL_FAILED', 'FAILED', 'CANCELLED'):
        run = _run(status=status)
        reconcile = FakeReconcileUseCase(result=replace(run, status='FAILED'))
        use_case = GetGenerationRunUseCase(
            generation_run_repository=cast(
                GenerationRunRepositoryPort, FakeGenerationRunRepository(run)
            ),
            reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
            reconcile_after_seconds=1,
        )

        assert use_case.execute(run.id) == run
        assert reconcile.calls == 0


def test_reconciles_immediately_when_threshold_zero() -> None:
    run = _run()
    reconciled = replace(run, status='SUCCEEDED')
    reconcile = FakeReconcileUseCase(result=reconciled)
    use_case = GetGenerationRunUseCase(
        generation_run_repository=cast(
            GenerationRunRepositoryPort, FakeGenerationRunRepository(run)
        ),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
        reconcile_after_seconds=0,
    )

    assert use_case.execute(run.id) == reconciled
    assert reconcile.calls == 1


def test_skips_reconcile_when_provider_identifiers_missing() -> None:
    for run in (_run(provider_request_id=None), _run(endpoint_id=None)):
        reconcile = FakeReconcileUseCase(result=replace(run, status='FAILED'))
        use_case = GetGenerationRunUseCase(
            generation_run_repository=cast(
                GenerationRunRepositoryPort, FakeGenerationRunRepository(run)
            ),
            reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, reconcile),
            reconcile_after_seconds=1,
        )

        assert use_case.execute(run.id) == run
        assert reconcile.calls == 0


def test_reconciles_only_after_threshold_age() -> None:
    old = _run(updated_at=datetime.now(UTC) - timedelta(seconds=120))
    fresh = _run(updated_at=datetime.now(UTC) - timedelta(seconds=5))

    old_reconcile = FakeReconcileUseCase(result=replace(old, status='SUCCEEDED'))
    old_use_case = GetGenerationRunUseCase(
        generation_run_repository=cast(
            GenerationRunRepositoryPort, FakeGenerationRunRepository(old)
        ),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, old_reconcile),
        reconcile_after_seconds=30,
    )
    old_result = old_use_case.execute(old.id)
    assert old_result is not None
    assert old_result.status == 'SUCCEEDED'
    assert old_reconcile.calls == 1

    fresh_reconcile = FakeReconcileUseCase(result=replace(fresh, status='SUCCEEDED'))
    fresh_use_case = GetGenerationRunUseCase(
        generation_run_repository=cast(
            GenerationRunRepositoryPort, FakeGenerationRunRepository(fresh)
        ),
        reconcile_generation_run_use_case=cast(ReconcileGenerationRunUseCase, fresh_reconcile),
        reconcile_after_seconds=30,
    )
    assert fresh_use_case.execute(fresh.id) == fresh
    assert fresh_reconcile.calls == 0
