from __future__ import annotations

from uuid import UUID, uuid4

from ai_video_gen_backend.domain.scene import Scene, SceneInput, SceneRepositoryPort


class SyncScenesUseCase:
    def __init__(self, scene_repository: SceneRepositoryPort) -> None:
        self._scene_repository = scene_repository

    def execute(self, project_id: UUID, scene_inputs: list[SceneInput]) -> list[Scene]:
        normalized_scenes = self._normalize_scenes(project_id, scene_inputs)
        self._scene_repository.bulk_replace(project_id, normalized_scenes)
        return normalized_scenes

    def _normalize_scenes(self, project_id: UUID, scene_inputs: list[SceneInput]) -> list[Scene]:
        if len(scene_inputs) == 0:
            return [self._create_default_scene(project_id=project_id, scene_number=1)]

        normalized: list[Scene] = []
        for index, scene_input in enumerate(scene_inputs):
            scene_number = index + 1
            name = scene_input.name.strip() if scene_input.name else ''
            if len(name) == 0:
                name = f'Untitled Scene {scene_number}'

            normalized.append(
                Scene(
                    id=scene_input.id or uuid4(),
                    project_id=project_id,
                    name=name,
                    scene_number=scene_number,
                    content=scene_input.content or self._empty_content(),
                )
            )

        return normalized

    def _create_default_scene(self, project_id: UUID, scene_number: int) -> Scene:
        return Scene(
            id=uuid4(),
            project_id=project_id,
            name=f'Untitled Scene {scene_number}',
            scene_number=scene_number,
            content=self._empty_content(),
        )

    def _empty_content(self) -> dict[str, object]:
        return {'text': ''}
