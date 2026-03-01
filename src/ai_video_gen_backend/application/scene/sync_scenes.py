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

            body = scene_input.body if isinstance(scene_input.body, str) else ''
            if len(body.strip()) == 0 and scene_input.content is not None:
                body = self._extract_text_from_node(scene_input.content).strip()

            normalized.append(
                Scene(
                    id=scene_input.id or uuid4(),
                    project_id=project_id,
                    name=name,
                    scene_number=scene_number,
                    body=body,
                    content=scene_input.content,
                )
            )

        return normalized

    def _create_default_scene(self, project_id: UUID, scene_number: int) -> Scene:
        return Scene(
            id=uuid4(),
            project_id=project_id,
            name=f'Untitled Scene {scene_number}',
            scene_number=scene_number,
            body='',
            content=None,
        )

    def _extract_text_from_node(self, node: object) -> str:
        if node is None:
            return ''

        if isinstance(node, str):
            return node

        if isinstance(node, list):
            text_parts = [self._extract_text_from_node(item) for item in node]
            return '\n'.join(filter(None, text_parts)).replace('\n\n\n', '\n\n')

        if not isinstance(node, dict):
            return ''

        node_type = node.get('type')
        if node_type == 'text':
            text_value = node.get('text')
            return text_value if isinstance(text_value, str) else ''

        content = node.get('content')
        if isinstance(content, list):
            if node_type == 'doc':
                blocks = [self._extract_text_from_node(block) for block in content]
                return '\n\n'.join(filter(None, blocks)).replace('\n\n\n', '\n\n')

            return ''.join(self._extract_text_from_node(child) for child in content)

        return ''
