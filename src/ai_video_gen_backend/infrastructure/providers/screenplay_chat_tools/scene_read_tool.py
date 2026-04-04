from __future__ import annotations

from langchain_core.tools import tool

from .runtime import ScreenplayToolsRuntime


def build_get_scene_tool(runtime: ScreenplayToolsRuntime) -> object:
    @tool('get_scene')
    def get_scene(id: str | None = None) -> dict[str, object]:
        """Return a scene's full XML content by id or active scene."""
        runtime.raise_if_cancelled()
        screenplay = runtime.get_screenplay()
        if isinstance(screenplay, dict):
            return screenplay

        resolved_scene_id, error = runtime.resolve_scene_id(id)
        if error is not None:
            return error
        if resolved_scene_id is None:
            return {
                'status': 'error',
                'code': 'missing_scene_id',
                'message': 'sceneId resolution failed unexpectedly',
            }

        for scene in screenplay.scenes:
            if scene.id == resolved_scene_id:
                return {
                    'status': 'ok',
                    'sceneId': str(scene.id),
                    'orderIndex': scene.order_index,
                    'content': scene.content,
                }

        return {
            'status': 'error',
            'code': 'scene_not_found',
            'message': 'Scene not found for screenplay',
        }

    return get_scene
