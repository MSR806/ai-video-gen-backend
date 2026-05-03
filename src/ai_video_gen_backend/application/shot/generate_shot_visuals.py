from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ai_video_gen_backend.application.shot.craft_shot_image_prompt import (
    ShotNotFoundError,
)
from ai_video_gen_backend.domain.collection import Collection
from ai_video_gen_backend.domain.generation import GenerationRunRequest, GenerationRunSubmission
from ai_video_gen_backend.domain.project import DEFAULT_PROJECT_ASPECT_RATIO, ProjectRepositoryPort
from ai_video_gen_backend.domain.screenplay import ScreenplayRepositoryPort
from ai_video_gen_backend.domain.shot import ShotImagePromptCraftResult, ShotRepositoryPort


class EnsureShotVisualCollectionPort(Protocol):
    def execute(self, *, project_id: UUID, scene_id: UUID, shot_id: UUID) -> Collection | None: ...


class CraftShotImagePromptPort(Protocol):
    def execute(self, *, project_id: UUID, collection_id: UUID) -> ShotImagePromptCraftResult: ...


class SubmitGenerationRunPort(Protocol):
    def execute(self, request: GenerationRunRequest) -> GenerationRunSubmission: ...


class ShotVisualsProjectNotFoundError(Exception):
    pass


class ShotVisualsSceneNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class GenerateShotVisualsRequest:
    project_id: UUID
    scene_id: UUID
    shot_ids: list[UUID]
    model_key: str
    operation_key: str
    prompt: str | None = None


@dataclass(frozen=True, slots=True)
class ShotVisualGenerationResult:
    shot_id: UUID
    collection_id: UUID | None
    run_id: UUID | None
    status: str
    error: str | None = None


class GenerateShotVisualsUseCase:
    def __init__(
        self,
        *,
        project_repository: ProjectRepositoryPort,
        screenplay_repository: ScreenplayRepositoryPort,
        shot_repository: ShotRepositoryPort,
        ensure_shot_visual_collection: EnsureShotVisualCollectionPort,
        craft_shot_image_prompt: CraftShotImagePromptPort,
        submit_generation_run: SubmitGenerationRunPort,
    ) -> None:
        self._project_repository = project_repository
        self._screenplay_repository = screenplay_repository
        self._shot_repository = shot_repository
        self._ensure_shot_visual_collection = ensure_shot_visual_collection
        self._craft_shot_image_prompt = craft_shot_image_prompt
        self._submit_generation_run = submit_generation_run

    def execute(self, request: GenerateShotVisualsRequest) -> list[ShotVisualGenerationResult]:
        project = self._project_repository.get_project_by_id(request.project_id)
        if project is None:
            raise ShotVisualsProjectNotFoundError

        screenplay = self._screenplay_repository.get_screenplay_by_project_id(request.project_id)
        if screenplay is None:
            raise ShotVisualsSceneNotFoundError

        if not any(scene.id == request.scene_id for scene in screenplay.scenes):
            raise ShotVisualsSceneNotFoundError

        aspect_ratio = project.aspect_ratio or DEFAULT_PROJECT_ASPECT_RATIO
        results: list[ShotVisualGenerationResult] = []

        for shot_id in request.shot_ids:
            shot = self._shot_repository.get_shot(request.scene_id, shot_id)
            if shot is None:
                results.append(
                    ShotVisualGenerationResult(
                        shot_id=shot_id,
                        collection_id=None,
                        run_id=None,
                        status='FAILED',
                        error='Shot not found',
                    )
                )
                continue

            collection = self._ensure_shot_visual_collection.execute(
                project_id=request.project_id,
                scene_id=request.scene_id,
                shot_id=shot_id,
            )
            if collection is None:
                results.append(
                    ShotVisualGenerationResult(
                        shot_id=shot_id,
                        collection_id=None,
                        run_id=None,
                        status='FAILED',
                        error='Shot visual collection not found',
                    )
                )
                continue

            try:
                prompt = request.prompt.strip() if request.prompt is not None else ''
                if len(prompt) == 0:
                    prompt = self._craft_shot_image_prompt.execute(
                        project_id=request.project_id,
                        collection_id=collection.id,
                    ).prompt

                submission = self._submit_generation_run.execute(
                    GenerationRunRequest(
                        project_id=request.project_id,
                        collection_id=collection.id,
                        model_key=request.model_key,
                        operation_key=request.operation_key,
                        inputs={
                            'prompt': prompt,
                            'aspect_ratio': aspect_ratio,
                        },
                        output_count=1,
                    )
                )
                results.append(
                    ShotVisualGenerationResult(
                        shot_id=shot_id,
                        collection_id=collection.id,
                        run_id=submission.run.id,
                        status=submission.run.status,
                    )
                )
            except ShotNotFoundError:
                results.append(
                    ShotVisualGenerationResult(
                        shot_id=shot_id,
                        collection_id=collection.id,
                        run_id=None,
                        status='FAILED',
                        error='Shot not found',
                    )
                )
            except Exception as exc:
                results.append(
                    ShotVisualGenerationResult(
                        shot_id=shot_id,
                        collection_id=collection.id,
                        run_id=None,
                        status='FAILED',
                        error=str(exc),
                    )
                )

        return results
