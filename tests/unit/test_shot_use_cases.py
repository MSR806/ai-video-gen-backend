from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ai_video_gen_backend.application.shot import (
    CreateShotUseCase,
    DeleteShotUseCase,
    ListShotsUseCase,
    ReorderShotsUseCase,
    UpdateShotUseCase,
)
from ai_video_gen_backend.domain.shot import Shot, ShotCreateInput, ShotUpdateInput


class FakeShotRepository:
    def __init__(self, shots: list[Shot]) -> None:
        self._shots = shots

    def list_shots(self, scene_id: UUID) -> list[Shot]:
        return [shot for shot in self._shots if shot.scene_id == scene_id]

    def create_shot(self, scene_id: UUID, payload: ShotCreateInput) -> Shot | None:
        order_index = len(self.list_shots(scene_id)) + 1
        shot = Shot(
            id=uuid4(),
            scene_id=scene_id,
            order_index=order_index,
            title=payload.title,
            description=payload.description,
            camera_framing=payload.camera_framing,
            camera_movement=payload.camera_movement,
            mood=payload.mood,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._shots.append(shot)
        return shot

    def update_shot(self, scene_id: UUID, shot_id: UUID, payload: ShotUpdateInput) -> Shot | None:
        for index, shot in enumerate(self._shots):
            if shot.id != shot_id or shot.scene_id != scene_id:
                continue

            updated = Shot(
                id=shot.id,
                scene_id=shot.scene_id,
                order_index=shot.order_index,
                title=payload.title if payload.title is not None else shot.title,
                description=payload.description
                if payload.description is not None
                else shot.description,
                camera_framing=(
                    payload.camera_framing
                    if payload.camera_framing is not None
                    else shot.camera_framing
                ),
                camera_movement=(
                    payload.camera_movement
                    if payload.camera_movement is not None
                    else shot.camera_movement
                ),
                mood=payload.mood if payload.mood is not None else shot.mood,
                created_at=shot.created_at,
                updated_at=datetime.now(UTC),
            )
            self._shots[index] = updated
            return updated

        return None

    def delete_shot(self, scene_id: UUID, shot_id: UUID) -> bool:
        for index, shot in enumerate(self._shots):
            if shot.id == shot_id and shot.scene_id == scene_id:
                del self._shots[index]
                return True
        return False

    def reorder_shots(self, scene_id: UUID, shot_ids: list[UUID]) -> list[Shot] | None:
        scene_shots = self.list_shots(scene_id)
        existing_ids = [shot.id for shot in scene_shots]
        if len(existing_ids) != len(shot_ids):
            return None
        if set(existing_ids) != set(shot_ids):
            return None

        order_by_id = {shot_id: index for index, shot_id in enumerate(shot_ids, start=1)}
        reordered: list[Shot] = []
        for shot in self._shots:
            if shot.scene_id != scene_id:
                continue
            reordered.append(
                Shot(
                    id=shot.id,
                    scene_id=shot.scene_id,
                    order_index=order_by_id[shot.id],
                    title=shot.title,
                    description=shot.description,
                    camera_framing=shot.camera_framing,
                    camera_movement=shot.camera_movement,
                    mood=shot.mood,
                    created_at=shot.created_at,
                    updated_at=datetime.now(UTC),
                )
            )

        for shot in reordered:
            for index, existing_shot in enumerate(self._shots):
                if existing_shot.id == shot.id:
                    self._shots[index] = shot
                    break

        return sorted(reordered, key=lambda shot: shot.order_index)


def _shot_fixture(scene_id: UUID, order_index: int) -> Shot:
    now = datetime.now(UTC)
    return Shot(
        id=uuid4(),
        scene_id=scene_id,
        order_index=order_index,
        title=f'Shot {order_index}',
        description='Description',
        camera_framing='Wide',
        camera_movement='Dolly in',
        mood='Tense',
        created_at=now,
        updated_at=now,
    )


def test_list_shots_use_case_returns_scene_shots() -> None:
    scene_id = uuid4()
    repo = FakeShotRepository([_shot_fixture(scene_id, 1), _shot_fixture(scene_id, 2)])

    result = ListShotsUseCase(repo).execute(scene_id)

    assert [shot.order_index for shot in result] == [1, 2]


def test_create_shot_use_case_creates_shot() -> None:
    scene_id = uuid4()
    repo = FakeShotRepository([])

    shot = CreateShotUseCase(repo).execute(
        scene_id,
        ShotCreateInput(
            title='Opening',
            description='Character enters frame',
            camera_framing='Medium',
            camera_movement='Static',
            mood='Calm',
        ),
    )

    assert shot is not None
    assert shot.order_index == 1
    assert shot.title == 'Opening'


def test_update_shot_use_case_returns_none_for_missing_shot() -> None:
    scene_id = uuid4()
    repo = FakeShotRepository([])

    result = UpdateShotUseCase(repo).execute(
        scene_id,
        uuid4(),
        ShotUpdateInput(title='Updated Title'),
    )

    assert result is None


def test_delete_shot_use_case_returns_false_for_missing_shot() -> None:
    scene_id = uuid4()
    repo = FakeShotRepository([])

    deleted = DeleteShotUseCase(repo).execute(scene_id, uuid4())

    assert deleted is False


def test_reorder_shots_use_case_rejects_incomplete_ids() -> None:
    scene_id = uuid4()
    shot_a = _shot_fixture(scene_id, 1)
    shot_b = _shot_fixture(scene_id, 2)
    repo = FakeShotRepository([shot_a, shot_b])

    reordered = ReorderShotsUseCase(repo).execute(scene_id, [shot_a.id])

    assert reordered is None
