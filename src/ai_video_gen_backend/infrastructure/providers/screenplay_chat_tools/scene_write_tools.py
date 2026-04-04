from __future__ import annotations

from langchain_core.tools import tool

from ai_video_gen_backend.domain.screenplay import (
    SceneXmlValidationError,
    ScreenplaySceneCreateInput,
    ScreenplaySceneUpdateInput,
)

from .runtime import ScreenplayToolsRuntime


def build_create_scene_tool(runtime: ScreenplayToolsRuntime) -> object:
    @tool('create_scene')
    def create_scene(content: str, position: int | None = None) -> dict[str, object]:
        """Create a new scene from validated scene XML content."""
        runtime.raise_if_cancelled()

        existing_screenplay = runtime.screenplay_repository.get_screenplay_by_project_id(
            runtime.screenplay_context.project_id
        )
        existing_scene_ids = (
            {scene.id for scene in existing_screenplay.scenes}
            if existing_screenplay is not None
            and existing_screenplay.id == runtime.screenplay_context.screenplay_id
            else set()
        )

        try:
            screenplay = runtime.screenplay_repository.create_screenplay_scene(
                runtime.screenplay_context.screenplay_id,
                ScreenplaySceneCreateInput(position=position, content=content),
            )
        except SceneXmlValidationError as exc:
            return {'status': 'error', 'code': 'invalid_scene_xml', 'message': str(exc)}

        if screenplay is None:
            return {
                'status': 'error',
                'code': 'screenplay_not_found',
                'message': 'Unable to create scene for missing screenplay',
            }

        runtime.mutation_tracker.did_mutate = True
        created_scene = next(
            (scene for scene in screenplay.scenes if scene.id not in existing_scene_ids),
            None,
        )
        return {
            'status': 'ok',
            'sceneId': str(created_scene.id) if created_scene is not None else None,
            'sceneCount': len(screenplay.scenes),
        }

    return create_scene


def build_update_scene_tool(runtime: ScreenplayToolsRuntime) -> object:
    @tool('update_scene')
    def update_scene(content: str, id: str | None = None) -> dict[str, object]:
        """Replace one scene's XML content in full."""
        runtime.raise_if_cancelled()

        resolved_scene_id, error = runtime.resolve_scene_id(id)
        if error is not None:
            return error
        if resolved_scene_id is None:
            return {
                'status': 'error',
                'code': 'missing_scene_id',
                'message': 'sceneId resolution failed unexpectedly',
            }

        try:
            scene = runtime.screenplay_repository.update_screenplay_scene(
                runtime.screenplay_context.screenplay_id,
                resolved_scene_id,
                ScreenplaySceneUpdateInput(content=content),
            )
        except SceneXmlValidationError as exc:
            return {'status': 'error', 'code': 'invalid_scene_xml', 'message': str(exc)}

        if scene is None:
            return {
                'status': 'error',
                'code': 'scene_not_found',
                'message': 'Unable to update scene that does not exist',
            }

        runtime.mutation_tracker.did_mutate = True
        return {
            'status': 'ok',
            'sceneId': str(scene.id),
            'orderIndex': scene.order_index,
            'summary': scene.content[:120],
        }

    return update_scene


def build_delete_scene_tool(runtime: ScreenplayToolsRuntime) -> object:
    @tool('delete_scene')
    def delete_scene(id: str | None = None) -> dict[str, object]:
        """Delete a scene by scene id."""
        runtime.raise_if_cancelled()

        resolved_scene_id, error = runtime.resolve_scene_id(id)
        if error is not None:
            return error
        if resolved_scene_id is None:
            return {
                'status': 'error',
                'code': 'missing_scene_id',
                'message': 'sceneId resolution failed unexpectedly',
            }

        screenplay = runtime.screenplay_repository.delete_screenplay_scene(
            runtime.screenplay_context.screenplay_id,
            resolved_scene_id,
        )
        if screenplay is None:
            return {
                'status': 'error',
                'code': 'scene_not_found',
                'message': 'Unable to delete scene that does not exist',
            }

        runtime.mutation_tracker.did_mutate = True
        return {
            'status': 'ok',
            'deletedSceneId': str(resolved_scene_id),
            'sceneCount': len(screenplay.scenes),
        }

    return delete_scene
