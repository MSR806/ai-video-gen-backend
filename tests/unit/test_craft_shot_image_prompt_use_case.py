from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ai_video_gen_backend.application.shot import (
    CraftShotImagePromptUseCase,
    ProjectNotFoundError,
    ScreenplaySceneNotFoundError,
    ShotNotFoundError,
)
from ai_video_gen_backend.domain.project import Project
from ai_video_gen_backend.domain.screenplay import Screenplay, ScreenplayScene
from ai_video_gen_backend.domain.shot import (
    Shot,
    ShotCreateInput,
    ShotImagePromptCraftRequest,
    ShotImagePromptCraftResult,
)


class FakeProjectRepository:
    def __init__(self, project: Project | None) -> None:
        self._project = project

    def get_all_projects(self) -> list[Project]:
        return []

    def get_project_by_id(self, project_id: UUID) -> Project | None:
        if self._project is None or self._project.id != project_id:
            return None
        return self._project

    def create_project(self, payload: object) -> Project:
        del payload
        raise NotImplementedError

    def update_project(self, project_id: UUID, payload: object) -> Project | None:
        del project_id, payload
        raise NotImplementedError


class FakeScreenplayRepository:
    def __init__(self, screenplay: Screenplay | None) -> None:
        self._screenplay = screenplay

    def get_screenplay_by_project_id(self, project_id: UUID) -> Screenplay | None:
        if self._screenplay is None or self._screenplay.project_id != project_id:
            return None
        return self._screenplay

    def create_screenplay(self, project_id: UUID, payload: object) -> Screenplay:
        del project_id, payload
        raise NotImplementedError

    def update_screenplay_title(self, screenplay_id: UUID, title: str) -> Screenplay | None:
        del screenplay_id, title
        raise NotImplementedError

    def create_screenplay_scene(self, screenplay_id: UUID, payload: object) -> Screenplay | None:
        del screenplay_id, payload
        raise NotImplementedError

    def update_screenplay_scene(
        self, screenplay_id: UUID, scene_id: UUID, payload: object
    ) -> ScreenplayScene | None:
        del screenplay_id, scene_id, payload
        raise NotImplementedError

    def delete_screenplay_scene(self, screenplay_id: UUID, scene_id: UUID) -> Screenplay | None:
        del screenplay_id, scene_id
        raise NotImplementedError

    def reorder_screenplay_scenes(
        self, screenplay_id: UUID, scene_ids: list[UUID]
    ) -> Screenplay | None:
        del screenplay_id, scene_ids
        raise NotImplementedError


class FakeShotRepository:
    def __init__(self, shot: Shot | None) -> None:
        self._shot = shot

    def get_shot_by_collection_id(self, collection_id: UUID) -> Shot | None:
        if self._shot is None or self._shot.collection_id != collection_id:
            return None
        return self._shot

    def list_shots(self, scene_id: UUID) -> list[Shot]:
        del scene_id
        return []

    def get_shot(self, scene_id: UUID, shot_id: UUID) -> Shot | None:
        del scene_id, shot_id
        return None

    def create_shot(self, scene_id: UUID, payload: object) -> Shot | None:
        del scene_id, payload
        raise NotImplementedError

    def update_shot(self, scene_id: UUID, shot_id: UUID, payload: object) -> Shot | None:
        del scene_id, shot_id, payload
        raise NotImplementedError

    def set_shot_collection(
        self, scene_id: UUID, shot_id: UUID, collection_id: UUID
    ) -> Shot | None:
        del scene_id, shot_id, collection_id
        raise NotImplementedError

    def delete_shot(self, scene_id: UUID, shot_id: UUID) -> bool:
        del scene_id, shot_id
        raise NotImplementedError

    def reorder_shots(self, scene_id: UUID, shot_ids: list[UUID]) -> list[Shot] | None:
        del scene_id, shot_ids
        raise NotImplementedError

    def replace_shots(self, scene_id: UUID, payloads: list[ShotCreateInput]) -> list[Shot] | None:
        del scene_id, payloads
        raise NotImplementedError


class FakePromptCrafter:
    def __init__(self) -> None:
        self.requests: list[ShotImagePromptCraftRequest] = []

    def craft_prompt(self, request: ShotImagePromptCraftRequest) -> ShotImagePromptCraftResult:
        self.requests.append(request)
        return ShotImagePromptCraftResult(prompt='crafted shot prompt')


def _project_fixture(style: str | None = 'grainy 35mm neo-noir') -> Project:
    now = datetime.now(UTC)
    return Project(
        id=uuid4(),
        name='Night Drive',
        description='A tense city drive',
        style=style,
        aspect_ratio='16:9',
        status='draft',
        created_at=now,
        updated_at=now,
    )


def test_craft_shot_image_prompt_uses_full_context_with_style() -> None:
    project = _project_fixture()
    scene_id = uuid4()
    screenplay = Screenplay(
        id=uuid4(),
        project_id=project.id,
        title='Pilot',
        scenes=[
            ScreenplayScene(
                id=scene_id,
                screenplay_id=uuid4(),
                order_index=1,
                content='scene xml',
            )
        ],
    )
    collection_id = uuid4()
    shot = Shot(
        id=uuid4(),
        scene_id=scene_id,
        collection_id=collection_id,
        order_index=1,
        title='Hero reveal',
        description='Character steps out under rain',
        camera_framing='Medium close-up',
        camera_movement='Slow dolly in',
        mood='Brooding',
    )
    prompt_crafter = FakePromptCrafter()
    use_case = CraftShotImagePromptUseCase(
        project_repository=FakeProjectRepository(project),
        screenplay_repository=FakeScreenplayRepository(screenplay),
        shot_repository=FakeShotRepository(shot),
        prompt_crafter=prompt_crafter,
    )

    result = use_case.execute(project_id=project.id, collection_id=collection_id)

    assert result.prompt == 'crafted shot prompt'
    assert prompt_crafter.requests[0].project_style == 'grainy 35mm neo-noir'
    assert prompt_crafter.requests[0].shot_title == 'Hero reveal'


def test_craft_shot_image_prompt_degrades_when_style_missing() -> None:
    project = _project_fixture(style=None)
    scene_id = uuid4()
    screenplay = Screenplay(
        id=uuid4(),
        project_id=project.id,
        title='Pilot',
        scenes=[
            ScreenplayScene(
                id=scene_id,
                screenplay_id=uuid4(),
                order_index=1,
                content='scene xml',
            )
        ],
    )
    collection_id = uuid4()
    shot = Shot(
        id=uuid4(),
        scene_id=scene_id,
        collection_id=collection_id,
        order_index=1,
        title='Hero reveal',
        description='Character steps out under rain',
        camera_framing='Medium close-up',
        camera_movement='Slow dolly in',
        mood='Brooding',
    )
    prompt_crafter = FakePromptCrafter()
    use_case = CraftShotImagePromptUseCase(
        project_repository=FakeProjectRepository(project),
        screenplay_repository=FakeScreenplayRepository(screenplay),
        shot_repository=FakeShotRepository(shot),
        prompt_crafter=prompt_crafter,
    )

    use_case.execute(project_id=project.id, collection_id=collection_id)

    assert prompt_crafter.requests[0].project_style is None


def test_craft_shot_image_prompt_bounded_scene_context() -> None:
    project = _project_fixture()
    scene_id = uuid4()
    long_scene = 'x' * 900
    screenplay = Screenplay(
        id=uuid4(),
        project_id=project.id,
        title='Pilot',
        scenes=[
            ScreenplayScene(
                id=scene_id,
                screenplay_id=uuid4(),
                order_index=1,
                content=long_scene,
            )
        ],
    )
    collection_id = uuid4()
    shot = Shot(
        id=uuid4(),
        scene_id=scene_id,
        collection_id=collection_id,
        order_index=1,
        title='Hero reveal',
        description='Character steps out under rain',
        camera_framing='Medium close-up',
        camera_movement='Slow dolly in',
        mood='Brooding',
    )
    prompt_crafter = FakePromptCrafter()
    use_case = CraftShotImagePromptUseCase(
        project_repository=FakeProjectRepository(project),
        screenplay_repository=FakeScreenplayRepository(screenplay),
        shot_repository=FakeShotRepository(shot),
        prompt_crafter=prompt_crafter,
    )

    use_case.execute(project_id=project.id, collection_id=collection_id)

    assert len(prompt_crafter.requests[0].scene_context) == 500


@pytest.mark.parametrize('missing', ['project', 'scene', 'shot'])
def test_craft_shot_image_prompt_raises_for_missing_context(missing: str) -> None:
    project = _project_fixture()
    scene_id = uuid4()
    collection_id = uuid4()
    shot = Shot(
        id=uuid4(),
        scene_id=scene_id,
        collection_id=collection_id,
        order_index=1,
        title='Hero reveal',
        description='Character steps out under rain',
        camera_framing='Medium close-up',
        camera_movement='Slow dolly in',
        mood='Brooding',
    )
    screenplay = Screenplay(
        id=uuid4(),
        project_id=project.id,
        title='Pilot',
        scenes=[
            ScreenplayScene(
                id=scene_id,
                screenplay_id=uuid4(),
                order_index=1,
                content='scene xml',
            )
        ],
    )

    project_repo = FakeProjectRepository(None if missing == 'project' else project)
    screenplay_repo = FakeScreenplayRepository(None if missing == 'scene' else screenplay)
    shot_repo = FakeShotRepository(None if missing == 'shot' else shot)
    use_case = CraftShotImagePromptUseCase(
        project_repository=project_repo,
        screenplay_repository=screenplay_repo,
        shot_repository=shot_repo,
        prompt_crafter=FakePromptCrafter(),
    )

    expected = {
        'project': ProjectNotFoundError,
        'scene': ScreenplaySceneNotFoundError,
        'shot': ShotNotFoundError,
    }[missing]
    with pytest.raises(expected):
        use_case.execute(project_id=project.id, collection_id=collection_id)
