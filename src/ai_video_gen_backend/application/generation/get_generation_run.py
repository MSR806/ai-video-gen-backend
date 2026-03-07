from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ai_video_gen_backend.domain.generation import GenerationRun, GenerationRunRepositoryPort

from .reconcile_generation_run import ReconcileGenerationRunUseCase


class GetGenerationRunUseCase:
    def __init__(
        self,
        generation_run_repository: GenerationRunRepositoryPort,
        reconcile_generation_run_use_case: ReconcileGenerationRunUseCase,
        *,
        reconcile_after_seconds: int,
    ) -> None:
        self._generation_run_repository = generation_run_repository
        self._reconcile_generation_run_use_case = reconcile_generation_run_use_case
        self._reconcile_after_seconds = max(reconcile_after_seconds, 0)

    def execute(self, run_id: UUID) -> GenerationRun | None:
        run = self._generation_run_repository.get_run_by_id(run_id)
        if run is None:
            return None

        if run.status in {'SUCCEEDED', 'PARTIAL_FAILED', 'FAILED', 'CANCELLED'}:
            return run

        if run.provider_request_id is None:
            return run

        if run.endpoint_id is None:
            return run

        if self._reconcile_after_seconds == 0:
            return self._reconcile_generation_run_use_case.execute(run)

        now = (
            datetime.now() if run.updated_at.tzinfo is None else datetime.now(run.updated_at.tzinfo)
        )
        age_seconds = (now - run.updated_at).total_seconds()
        if age_seconds >= self._reconcile_after_seconds:
            return self._reconcile_generation_run_use_case.execute(run)

        return run
