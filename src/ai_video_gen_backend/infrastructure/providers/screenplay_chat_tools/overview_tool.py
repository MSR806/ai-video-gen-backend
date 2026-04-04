from __future__ import annotations

from langchain_core.tools import tool

from .runtime import ScreenplayToolsRuntime


def build_get_screenplay_overview_tool(runtime: ScreenplayToolsRuntime) -> object:
    @tool('get_screenplay_overview')
    def get_screenplay_overview() -> dict[str, object]:
        """Return screenplay metadata and scene summaries."""
        runtime.raise_if_cancelled()
        screenplay = runtime.get_screenplay()
        if isinstance(screenplay, dict):
            return screenplay

        scenes = screenplay.scenes
        return {
            'status': 'ok',
            'screenplayId': str(screenplay.id),
            'projectId': str(screenplay.project_id),
            'title': screenplay.title,
            'sceneCount': len(scenes),
            'activeSceneId': (
                str(runtime.screenplay_context.active_scene_id)
                if runtime.screenplay_context.active_scene_id is not None
                else None
            ),
            'scenes': [
                {
                    'id': str(scene.id),
                    'orderIndex': scene.order_index,
                    'preview': scene.content[:120],
                }
                for scene in scenes
            ],
        }

    return get_screenplay_overview
