from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from ai_video_gen_backend.domain.generation import (
    GenerationJob,
    GenerationJobRepositoryPort,
    GenerationStatus,
)

from .reconcile_generation_job import ReconcileGenerationJobUseCase


class ListGenerationJobsUseCase:
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

    def execute(
        self,
        *,
        collection_id: UUID | None = None,
        project_id: UUID | None = None,
        statuses: list[GenerationStatus] | None = None,
        limit: int = 50,
    ) -> list[GenerationJob]:
        jobs = self._generation_job_repository.list_jobs(
            collection_id=collection_id,
            project_id=project_id,
            statuses=statuses,
            limit=limit,
        )

        threshold = datetime.now(UTC) - timedelta(seconds=self._reconcile_after_seconds)
        reconciled_jobs: list[GenerationJob] = []
        for job in jobs:
            updated_at = (
                job.updated_at
                if job.updated_at.tzinfo is not None
                else job.updated_at.replace(tzinfo=UTC)
            )
            if job.status in {'SUCCEEDED', 'FAILED', 'CANCELLED'} or updated_at > threshold:
                reconciled_jobs.append(job)
                continue

            reconciled_jobs.append(self._reconcile_generation_job_use_case.execute(job))

        return reconciled_jobs
