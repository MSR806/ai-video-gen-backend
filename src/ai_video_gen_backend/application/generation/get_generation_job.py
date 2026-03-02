from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from ai_video_gen_backend.domain.generation import GenerationJob, GenerationJobRepositoryPort

from .reconcile_generation_job import ReconcileGenerationJobUseCase


class GetGenerationJobUseCase:
    def __init__(
        self,
        generation_job_repository: GenerationJobRepositoryPort,
        reconcile_generation_job_use_case: ReconcileGenerationJobUseCase,
        *,
        reconcile_after_seconds: int,
    ) -> None:
        self._generation_job_repository = generation_job_repository
        self._reconcile_generation_job_use_case = reconcile_generation_job_use_case
        self._reconcile_after_seconds = reconcile_after_seconds

    def execute(self, job_id: UUID) -> GenerationJob | None:
        job = self._generation_job_repository.get_by_id(job_id)
        if job is None:
            return None

        if job.status in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:
            return job

        threshold = datetime.now(UTC) - timedelta(seconds=self._reconcile_after_seconds)
        updated_at = (
            job.updated_at
            if job.updated_at.tzinfo is not None
            else job.updated_at.replace(tzinfo=UTC)
        )
        if updated_at > threshold:
            return job

        return self._reconcile_generation_job_use_case.execute(job)
