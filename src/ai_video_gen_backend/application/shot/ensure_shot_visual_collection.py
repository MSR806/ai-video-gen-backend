from __future__ import annotations

import re
from uuid import UUID

from ai_video_gen_backend.domain.collection import (
    Collection,
    CollectionCreationPayload,
    CollectionRepositoryPort,
)
from ai_video_gen_backend.domain.screenplay import ScreenplayRepositoryPort
from ai_video_gen_backend.domain.shot import ShotRepositoryPort

AUTO_SCENE_COLLECTION_DESCRIPTION = 'Auto-created scene visual collection'
AUTO_SHOT_COLLECTION_DESCRIPTION = 'Auto-created shot visual collection'

_SCENE_MARKER_PREFIX = '[auto_scene_parent]'
_SHOT_MARKER_PREFIX = '[auto_shot_child]'


def _scene_collection_description(*, scene_id: UUID) -> str:
    return f'{AUTO_SCENE_COLLECTION_DESCRIPTION} {_SCENE_MARKER_PREFIX} scene_id={scene_id}'


def _shot_collection_description(*, scene_id: UUID, shot_id: UUID) -> str:
    return (
        f'{AUTO_SHOT_COLLECTION_DESCRIPTION} {_SHOT_MARKER_PREFIX} '
        f'scene_id={scene_id} shot_id={shot_id}'
    )


def _description_has_marker(description: str, *, marker_prefix: str, expected_id: UUID) -> bool:
    marker = f'{marker_prefix} scene_id={expected_id}'
    return marker in description


def _description_has_shot_marker(description: str, *, scene_id: UUID, shot_id: UUID) -> bool:
    marker = f'{_SHOT_MARKER_PREFIX} scene_id={scene_id} shot_id={shot_id}'
    return marker in description


class EnsureShotVisualCollectionUseCase:
    def __init__(
        self,
        *,
        shot_repository: ShotRepositoryPort,
        screenplay_repository: ScreenplayRepositoryPort,
        collection_repository: CollectionRepositoryPort,
    ) -> None:
        self._shot_repository = shot_repository
        self._screenplay_repository = screenplay_repository
        self._collection_repository = collection_repository

    def execute(self, *, project_id: UUID, scene_id: UUID, shot_id: UUID) -> Collection | None:
        screenplay = self._screenplay_repository.get_screenplay_by_project_id(project_id)
        if screenplay is None:
            return None

        scene = next((item for item in screenplay.scenes if item.id == scene_id), None)
        if scene is None:
            return None

        shot = self._shot_repository.get_shot(scene_id, shot_id)
        if shot is None:
            return None

        if shot.collection_id is not None:
            return self._collection_repository.get_collection_by_id(shot.collection_id)

        scene_collection_name = self._build_scene_collection_name(scene.order_index, scene.content)
        scene_collection = self._resolve_scene_collection(
            project_id=project_id,
            scene_id=scene_id,
        )
        if scene_collection is None:
            scene_collection = self._collection_repository.create_collection(
                CollectionCreationPayload(
                    project_id=project_id,
                    parent_collection_id=None,
                    name=scene_collection_name,
                    tag='scene',
                    description=_scene_collection_description(scene_id=scene_id),
                )
            )

        shot_collection_name = self._build_shot_collection_name(
            order_index=shot.order_index,
            title=shot.title,
            description=shot.description,
        )
        existing_shot_collection = self._find_unlinked_shot_collection(
            scene_id=scene_id,
            shot_id=shot_id,
            scene_collection_id=scene_collection.id,
            shot_collection_name=shot_collection_name,
        )
        if existing_shot_collection is not None:
            linked_shot = self._shot_repository.set_shot_collection(
                scene_id=scene_id,
                shot_id=shot_id,
                collection_id=existing_shot_collection.id,
            )
            if linked_shot is None:
                return None
            return existing_shot_collection

        shot_collection = self._collection_repository.create_collection(
            CollectionCreationPayload(
                project_id=project_id,
                parent_collection_id=scene_collection.id,
                name=shot_collection_name,
                tag='shot',
                description=_shot_collection_description(scene_id=scene_id, shot_id=shot_id),
            )
        )
        linked_shot = self._shot_repository.set_shot_collection(
            scene_id=scene_id,
            shot_id=shot_id,
            collection_id=shot_collection.id,
        )
        if linked_shot is None:
            return None

        return shot_collection

    def _find_unlinked_shot_collection(
        self,
        *,
        scene_id: UUID,
        shot_id: UUID,
        scene_collection_id: UUID,
        shot_collection_name: str,
    ) -> Collection | None:
        linked_collection_ids = {
            scene_shot.collection_id
            for scene_shot in self._shot_repository.list_shots(scene_id)
            if scene_shot.collection_id is not None
        }
        for child_collection in self._collection_repository.get_child_collections(
            scene_collection_id
        ):
            if child_collection.tag != 'shot':
                continue
            if _description_has_shot_marker(
                child_collection.description,
                scene_id=scene_id,
                shot_id=shot_id,
            ):
                return child_collection
            if child_collection.name != shot_collection_name:
                continue
            if child_collection.id in linked_collection_ids:
                continue
            return child_collection
        return None

    def _resolve_scene_collection(
        self,
        *,
        project_id: UUID,
        scene_id: UUID,
    ) -> Collection | None:
        for scene_shot in self._shot_repository.list_shots(scene_id):
            if scene_shot.collection_id is None:
                continue
            child_collection = self._collection_repository.get_collection_by_id(
                scene_shot.collection_id
            )
            if child_collection is None:
                continue
            parent_collection_id = child_collection.parent_collection_id
            if parent_collection_id is None:
                continue
            parent_collection = self._collection_repository.get_collection_by_id(
                parent_collection_id
            )
            if parent_collection is None:
                continue
            if parent_collection.project_id != project_id:
                continue
            if parent_collection.tag != 'scene':
                continue
            if parent_collection.parent_collection_id is not None:
                continue
            if not _description_has_marker(
                parent_collection.description,
                marker_prefix=_SCENE_MARKER_PREFIX,
                expected_id=scene_id,
            ):
                continue
            return parent_collection

        for project_collection in self._collection_repository.get_collections_by_project_id(
            project_id
        ):
            if project_collection.tag != 'scene':
                continue
            if project_collection.parent_collection_id is not None:
                continue
            if not _description_has_marker(
                project_collection.description,
                marker_prefix=_SCENE_MARKER_PREFIX,
                expected_id=scene_id,
            ):
                continue
            return project_collection

        return None

    def _build_scene_collection_name(self, order_index: int, scene_content: str) -> str:
        heading = self._extract_scene_heading(scene_content)
        if heading is not None:
            return f'Scene: {heading}'
        return f'Scene {order_index}'

    def _build_shot_collection_name(self, *, order_index: int, title: str, description: str) -> str:
        label = title.strip() or description.strip()
        if label:
            return f'Shot {order_index}: {label}'
        return f'Shot {order_index}'

    def _extract_scene_heading(self, scene_content: str) -> str | None:
        for match in re.finditer(r'>\s*([^<]+?)\s*<', scene_content):
            cleaned = match.group(1).strip()
            if cleaned:
                return cleaned
        return None
