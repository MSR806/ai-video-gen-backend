from __future__ import annotations

from uuid import UUID, uuid4

from ai_video_gen_backend.application.scene import (
    CreateSceneUseCase,
    DeleteSceneUseCase,
    UpdateSceneUseCase,
)
from ai_video_gen_backend.domain.scene import Scene, SceneCreateInput, SceneUpdateInput


class FakeSceneRepository:
    def __init__(self) -> None:
        self.created_project_id: UUID | None = None
        self.create_payload: SceneCreateInput | None = None
        self.updated_project_id: UUID | None = None
        self.updated_scene_id: UUID | None = None
        self.update_payload: SceneUpdateInput | None = None
        self.deleted_project_id: UUID | None = None
        self.deleted_scene_id: UUID | None = None

    def get_scenes_by_project_id(self, project_id: UUID) -> list[Scene]:
        del project_id
        return []

    def get_scene_by_id(self, scene_id: UUID) -> Scene | None:
        del scene_id
        return None

    def create_scene(self, project_id: UUID, payload: SceneCreateInput) -> list[Scene]:
        self.created_project_id = project_id
        self.create_payload = payload
        return []

    def update_scene(
        self,
        project_id: UUID,
        scene_id: UUID,
        payload: SceneUpdateInput,
    ) -> Scene | None:
        self.updated_project_id = project_id
        self.updated_scene_id = scene_id
        self.update_payload = payload
        return None

    def delete_scene(self, project_id: UUID, scene_id: UUID) -> list[Scene] | None:
        self.deleted_project_id = project_id
        self.deleted_scene_id = scene_id
        return []


def test_create_scene_use_case_delegates_to_repository() -> None:
    repository = FakeSceneRepository()
    use_case = CreateSceneUseCase(repository)
    project_id = uuid4()
    payload = SceneCreateInput(id=uuid4(), position=2, name='Intro', content={'text': 'A'})

    created = use_case.execute(project_id, payload)

    assert created == []
    assert repository.created_project_id == project_id
    assert repository.create_payload == payload


def test_update_scene_use_case_delegates_to_repository() -> None:
    repository = FakeSceneRepository()
    use_case = UpdateSceneUseCase(repository)
    project_id = uuid4()
    scene_id = uuid4()
    payload = SceneUpdateInput(
        name='Updated',
        content={'text': 'Updated content'},
        update_name=True,
        update_content=True,
    )

    updated = use_case.execute(project_id, scene_id, payload)

    assert updated is None
    assert repository.updated_project_id == project_id
    assert repository.updated_scene_id == scene_id
    assert repository.update_payload == payload


def test_delete_scene_use_case_delegates_to_repository() -> None:
    repository = FakeSceneRepository()
    use_case = DeleteSceneUseCase(repository)
    project_id = uuid4()
    scene_id = uuid4()

    deleted = use_case.execute(project_id, scene_id)

    assert deleted == []
    assert repository.deleted_project_id == project_id
    assert repository.deleted_scene_id == scene_id
