from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.domain.chat import (
    ChatStreamCancelledError,
    ScreenplayChatContext,
)
from ai_video_gen_backend.domain.screenplay import (
    Screenplay,
    ScreenplayCreateInput,
    ScreenplayScene,
    ScreenplaySceneCreateInput,
    ScreenplaySceneUpdateInput,
)
from ai_video_gen_backend.infrastructure.providers.screenplay_chat_tools import (
    ScreenplayMutationTracker,
    build_screenplay_tools,
)


class _FakeScreenplayRepository:
    def __init__(self, *, screenplay: Screenplay, raise_internal: bool = False) -> None:
        self._screenplay = screenplay
        self._raise_internal = raise_internal
        self.create_scene_calls = 0

    def get_screenplay_by_project_id(self, project_id: UUID) -> Screenplay | None:
        if project_id != self._screenplay.project_id:
            return None
        return self._screenplay

    def create_screenplay(self, project_id: UUID, payload: ScreenplayCreateInput) -> Screenplay:
        del project_id, payload
        raise NotImplementedError

    def update_screenplay_title(self, screenplay_id: UUID, title: str) -> Screenplay | None:
        del screenplay_id, title
        return None

    def create_screenplay_scene(
        self,
        screenplay_id: UUID,
        payload: ScreenplaySceneCreateInput,
    ) -> Screenplay | None:
        del screenplay_id, payload
        self.create_scene_calls += 1
        if self._raise_internal:
            raise RuntimeError('db internals leaked')
        return self._screenplay

    def update_screenplay_scene(
        self,
        screenplay_id: UUID,
        scene_id: UUID,
        payload: ScreenplaySceneUpdateInput,
    ) -> ScreenplayScene | None:
        del screenplay_id, scene_id, payload
        return None

    def delete_screenplay_scene(self, screenplay_id: UUID, scene_id: UUID) -> Screenplay | None:
        del screenplay_id, scene_id
        return None

    def reorder_screenplay_scenes(
        self,
        screenplay_id: UUID,
        scene_ids: list[UUID],
    ) -> Screenplay | None:
        del screenplay_id, scene_ids
        return None


def _build_screenplay() -> Screenplay:
    screenplay_id = uuid4()
    return Screenplay(
        id=screenplay_id,
        project_id=uuid4(),
        title='Pilot',
        scenes=[
            ScreenplayScene(
                id=uuid4(),
                screenplay_id=screenplay_id,
                order_index=0,
                content='<scene><slugline>INT. LAB - DAY</slugline></scene>',
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _create_scene_tool(tools: list[object]) -> object:
    for tool in tools:
        name = getattr(tool, 'name', None)
        if name == 'create_scene':
            return tool
    msg = 'create_scene tool not found'
    raise AssertionError(msg)


class _InvokableTool(Protocol):
    def invoke(self, input: dict[str, object]) -> dict[str, object]: ...


def test_create_scene_tool_respects_stream_cancellation() -> None:
    screenplay = _build_screenplay()
    repository = _FakeScreenplayRepository(screenplay=screenplay)

    tools = build_screenplay_tools(
        screenplay_repository=repository,
        screenplay_context=ScreenplayChatContext(
            project_id=screenplay.project_id,
            screenplay_id=screenplay.id,
            active_scene_id=None,
        ),
        mutation_tracker=ScreenplayMutationTracker(),
        is_cancelled=lambda: True,
    )
    create_tool = cast(_InvokableTool, _create_scene_tool(tools))

    with pytest.raises(ChatStreamCancelledError):
        create_tool.invoke({'content': '<scene><slugline>INT. LAB - NIGHT</slugline></scene>'})

    assert repository.create_scene_calls == 0


def test_create_scene_tool_sanitizes_internal_exception_message() -> None:
    screenplay = _build_screenplay()
    repository = _FakeScreenplayRepository(screenplay=screenplay, raise_internal=True)

    tools = build_screenplay_tools(
        screenplay_repository=repository,
        screenplay_context=ScreenplayChatContext(
            project_id=screenplay.project_id,
            screenplay_id=screenplay.id,
            active_scene_id=None,
        ),
        mutation_tracker=ScreenplayMutationTracker(),
        is_cancelled=lambda: False,
    )
    create_tool = cast(_InvokableTool, _create_scene_tool(tools))

    with pytest.raises(RuntimeError, match='db internals leaked'):
        create_tool.invoke({'content': '<scene><slugline>INT. LAB - NIGHT</slugline></scene>'})
