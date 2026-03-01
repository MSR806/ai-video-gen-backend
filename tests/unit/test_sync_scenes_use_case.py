from __future__ import annotations

from uuid import UUID, uuid4

from ai_video_gen_backend.application.scene import SyncScenesUseCase
from ai_video_gen_backend.domain.scene import Scene, SceneInput


class FakeSceneRepository:
    def __init__(self) -> None:
        self.project_id: UUID | None = None
        self.saved_scenes: list[Scene] = []

    def get_scenes_by_project_id(self, project_id: UUID) -> list[Scene]:
        del project_id
        return []

    def get_scene_by_id(self, scene_id: UUID) -> Scene | None:
        del scene_id
        return None

    def bulk_replace(self, project_id: UUID, scenes: list[Scene]) -> None:
        self.project_id = project_id
        self.saved_scenes = scenes


def test_sync_scenes_creates_default_scene_when_payload_is_empty() -> None:
    repository = FakeSceneRepository()
    use_case = SyncScenesUseCase(repository)
    project_id = uuid4()

    normalized = use_case.execute(project_id, [])

    assert repository.project_id == project_id
    assert len(normalized) == 1
    assert normalized[0].scene_number == 1
    assert normalized[0].name == 'Untitled Scene 1'
    assert normalized[0].content == {'text': ''}


def test_sync_scenes_normalizes_order_and_defaults_content() -> None:
    repository = FakeSceneRepository()
    use_case = SyncScenesUseCase(repository)
    project_id = uuid4()

    inputs = [
        SceneInput(
            id=uuid4(),
            name='  ',
            content={'text': 'First line\n\nSecond line'},
        ),
        SceneInput(name='Closing'),
    ]

    normalized = use_case.execute(project_id, inputs)

    assert len(normalized) == 2
    assert normalized[0].scene_number == 1
    assert normalized[0].name == 'Untitled Scene 1'
    assert normalized[0].content == {'text': 'First line\n\nSecond line'}
    assert normalized[1].scene_number == 2
    assert normalized[1].name == 'Closing'
    assert normalized[1].content == {'text': ''}
