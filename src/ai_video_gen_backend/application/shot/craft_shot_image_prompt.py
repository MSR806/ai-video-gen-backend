from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.project import ProjectRepositoryPort
from ai_video_gen_backend.domain.screenplay import ScreenplayRepositoryPort
from ai_video_gen_backend.domain.shot import (
    ShotImagePromptCrafterPort,
    ShotImagePromptCraftRequest,
    ShotImagePromptCraftResult,
    ShotRepositoryPort,
)

_MAX_SCENE_CONTEXT_CHARS = 500


class ProjectNotFoundError(Exception):
    pass


class ScreenplaySceneNotFoundError(Exception):
    pass


class ShotNotFoundError(Exception):
    pass


class CraftShotImagePromptUseCase:
    def __init__(
        self,
        *,
        project_repository: ProjectRepositoryPort,
        screenplay_repository: ScreenplayRepositoryPort,
        shot_repository: ShotRepositoryPort,
        prompt_crafter: ShotImagePromptCrafterPort,
    ) -> None:
        self._project_repository = project_repository
        self._screenplay_repository = screenplay_repository
        self._shot_repository = shot_repository
        self._prompt_crafter = prompt_crafter

    def execute(self, *, project_id: UUID, collection_id: UUID) -> ShotImagePromptCraftResult:
        project = self._project_repository.get_project_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError

        screenplay = self._screenplay_repository.get_screenplay_by_project_id(project_id)
        if screenplay is None:
            raise ScreenplaySceneNotFoundError

        shot = self._shot_repository.get_shot_by_collection_id(collection_id)
        if shot is None:
            raise ShotNotFoundError

        scene = next((item for item in screenplay.scenes if item.id == shot.scene_id), None)
        if scene is None:
            raise ScreenplaySceneNotFoundError

        return self._prompt_crafter.craft_prompt(
            ShotImagePromptCraftRequest(
                project_name=project.name,
                project_style=project.style,
                shot_title=shot.title,
                shot_description=shot.description,
                camera_framing=shot.camera_framing,
                camera_movement=shot.camera_movement,
                mood=shot.mood,
                scene_context=scene.content[:_MAX_SCENE_CONTEXT_CHARS],
            )
        )
