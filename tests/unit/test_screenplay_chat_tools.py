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
    def __init__(
        self,
        *,
        screenplay: Screenplay,
        raise_internal: bool = False,
        update_returns_scene: bool = False,
        delete_returns_screenplay: bool = False,
    ) -> None:
        self._screenplay = screenplay
        self._raise_internal = raise_internal
        self._update_returns_scene = update_returns_scene
        self._delete_returns_screenplay = delete_returns_screenplay
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
        del screenplay_id, payload
        if not self._update_returns_scene:
            return None
        return next((scene for scene in self._screenplay.scenes if scene.id == scene_id), None)

    def delete_screenplay_scene(self, screenplay_id: UUID, scene_id: UUID) -> Screenplay | None:
        del screenplay_id, scene_id
        if self._delete_returns_screenplay:
            return self._screenplay
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


def _tool_by_name(tools: list[object], name: str) -> object:
    for tool in tools:
        tool_name = getattr(tool, 'name', None)
        if tool_name == name:
            return tool
    msg = f'{name} tool not found'
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
    create_tool = cast(_InvokableTool, _tool_by_name(tools, 'create_scene'))

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
    create_tool = cast(_InvokableTool, _tool_by_name(tools, 'create_scene'))

    with pytest.raises(RuntimeError, match='db internals leaked'):
        create_tool.invoke({'content': '<scene><slugline>INT. LAB - NIGHT</slugline></scene>'})


def test_get_scene_tool_returns_active_scene_when_no_id_is_passed() -> None:
    screenplay = _build_screenplay()
    repository = _FakeScreenplayRepository(screenplay=screenplay)
    active_scene = screenplay.scenes[0]

    tools = build_screenplay_tools(
        screenplay_repository=repository,
        screenplay_context=ScreenplayChatContext(
            project_id=screenplay.project_id,
            screenplay_id=screenplay.id,
            active_scene_id=active_scene.id,
        ),
        mutation_tracker=ScreenplayMutationTracker(),
        is_cancelled=lambda: False,
    )
    get_scene_tool = cast(_InvokableTool, _tool_by_name(tools, 'get_scene'))

    result = get_scene_tool.invoke({})

    assert result['status'] == 'ok'
    assert result['sceneId'] == str(active_scene.id)
    assert result['content'] == active_scene.content


def test_update_and_delete_tools_report_not_found_without_mutation() -> None:
    screenplay = _build_screenplay()
    repository = _FakeScreenplayRepository(screenplay=screenplay)
    tracker = ScreenplayMutationTracker()

    tools = build_screenplay_tools(
        screenplay_repository=repository,
        screenplay_context=ScreenplayChatContext(
            project_id=screenplay.project_id,
            screenplay_id=screenplay.id,
            active_scene_id=None,
        ),
        mutation_tracker=tracker,
        is_cancelled=lambda: False,
    )

    update_scene_tool = cast(_InvokableTool, _tool_by_name(tools, 'update_scene'))
    delete_scene_tool = cast(_InvokableTool, _tool_by_name(tools, 'delete_scene'))

    update_result = update_scene_tool.invoke(
        {'id': str(screenplay.scenes[0].id), 'content': '<scene><action>Updated</action></scene>'}
    )
    delete_result = delete_scene_tool.invoke({'id': str(screenplay.scenes[0].id)})

    assert update_result == {
        'status': 'error',
        'code': 'scene_not_found',
        'message': 'Unable to update scene that does not exist',
    }
    assert delete_result == {
        'status': 'error',
        'code': 'scene_not_found',
        'message': 'Unable to delete scene that does not exist',
    }
    assert tracker.did_mutate is False
