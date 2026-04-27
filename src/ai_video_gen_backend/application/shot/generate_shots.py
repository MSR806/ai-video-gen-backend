from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.screenplay import ScreenplayRepositoryPort
from ai_video_gen_backend.domain.shot import Shot, ShotGenerationPort, ShotRepositoryPort


class InvalidShotGenerationError(Exception):
    pass


class GenerateShotsUseCase:
    def __init__(
        self,
        *,
        shot_repository: ShotRepositoryPort,
        screenplay_repository: ScreenplayRepositoryPort,
        shot_generator: ShotGenerationPort,
    ) -> None:
        self._shot_repository = shot_repository
        self._screenplay_repository = screenplay_repository
        self._shot_generator = shot_generator

    def execute(self, *, project_id: UUID, scene_id: UUID) -> list[Shot] | None:
        screenplay = self._screenplay_repository.get_screenplay_by_project_id(project_id)
        if screenplay is None:
            return None

        scene = next((item for item in screenplay.scenes if item.id == scene_id), None)
        if scene is None:
            return None

        try:
            payloads = self._shot_generator.generate_shots(scene.content)
        except Exception as exc:
            raise InvalidShotGenerationError(f'Failed to generate shots: {exc}') from exc

        replaced = self._shot_repository.replace_shots(scene_id, payloads)
        if replaced is None:
            return None

        return sorted(replaced, key=lambda shot: shot.order_index)
