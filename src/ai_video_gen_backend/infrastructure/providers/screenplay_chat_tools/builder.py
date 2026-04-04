from __future__ import annotations

from collections.abc import Callable

from ai_video_gen_backend.domain.chat import ScreenplayChatContext
from ai_video_gen_backend.domain.screenplay import ScreenplayRepositoryPort

from .overview_tool import build_get_screenplay_overview_tool
from .runtime import ScreenplayMutationTracker, ScreenplayToolsRuntime
from .scene_read_tool import build_get_scene_tool
from .scene_write_tools import (
    build_create_scene_tool,
    build_delete_scene_tool,
    build_update_scene_tool,
)


def build_screenplay_tools(
    *,
    screenplay_repository: ScreenplayRepositoryPort,
    screenplay_context: ScreenplayChatContext,
    mutation_tracker: ScreenplayMutationTracker,
    is_cancelled: Callable[[], bool] | None = None,
) -> list[object]:
    runtime = ScreenplayToolsRuntime(
        screenplay_repository=screenplay_repository,
        screenplay_context=screenplay_context,
        mutation_tracker=mutation_tracker,
        is_cancelled=is_cancelled,
    )
    return [
        build_get_screenplay_overview_tool(runtime),
        build_get_scene_tool(runtime),
        build_create_scene_tool(runtime),
        build_update_scene_tool(runtime),
        build_delete_scene_tool(runtime),
    ]
