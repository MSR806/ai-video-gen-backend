from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.shot import Shot, ShotCreateInput, ShotUpdateInput
from ai_video_gen_backend.infrastructure.db.models import ScreenplaySceneModel, ShotModel


class ShotSqlRepository:
    _shot_order_shift = 1000000

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_shots(self, scene_id: UUID) -> list[Shot]:
        stmt = (
            select(ShotModel)
            .where(ShotModel.scene_id == scene_id)
            .order_by(ShotModel.order_index.asc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(model) for model in models]

    def create_shot(self, scene_id: UUID, payload: ShotCreateInput) -> Shot | None:
        try:
            if self._lock_scene(scene_id) is None:
                return None

            order_index = self._count_shots(scene_id) + 1
            model = ShotModel(
                id=uuid4(),
                scene_id=scene_id,
                order_index=order_index,
                title=payload.title,
                description=payload.description,
                camera_framing=payload.camera_framing,
                camera_movement=payload.camera_movement,
                mood=payload.mood,
            )
            self._session.add(model)
            self._session.commit()
            self._session.refresh(model)
            return self._to_domain(model)
        except Exception:
            self._session.rollback()
            raise

    def update_shot(self, scene_id: UUID, shot_id: UUID, payload: ShotUpdateInput) -> Shot | None:
        try:
            stmt = select(ShotModel).where(ShotModel.id == shot_id, ShotModel.scene_id == scene_id)
            model = self._session.execute(stmt).scalar_one_or_none()
            if model is None:
                return None

            if payload.title is not None:
                model.title = payload.title
            if payload.description is not None:
                model.description = payload.description
            if payload.camera_framing is not None:
                model.camera_framing = payload.camera_framing
            if payload.camera_movement is not None:
                model.camera_movement = payload.camera_movement
            if payload.mood is not None:
                model.mood = payload.mood

            self._session.commit()
            self._session.refresh(model)
            return self._to_domain(model)
        except Exception:
            self._session.rollback()
            raise

    def delete_shot(self, scene_id: UUID, shot_id: UUID) -> bool:
        try:
            if self._lock_scene(scene_id) is None:
                return False

            stmt = select(ShotModel).where(ShotModel.id == shot_id, ShotModel.scene_id == scene_id)
            model = self._session.execute(stmt).scalar_one_or_none()
            if model is None:
                return False

            deleted_order_index = model.order_index
            self._session.delete(model)
            self._session.flush()
            self._shift_shot_order_down(scene_id, deleted_order_index)

            self._session.commit()
            return True
        except Exception:
            self._session.rollback()
            raise

    def reorder_shots(self, scene_id: UUID, shot_ids: list[UUID]) -> list[Shot] | None:
        try:
            if self._lock_scene(scene_id) is None:
                return None

            existing_stmt = (
                select(ShotModel.id)
                .where(ShotModel.scene_id == scene_id)
                .order_by(ShotModel.order_index.asc())
            )
            existing_ids = list(self._session.execute(existing_stmt).scalars().all())

            if len(existing_ids) != len(shot_ids):
                return None

            if set(existing_ids) != set(shot_ids):
                return None

            for order_index, shot_id in enumerate(shot_ids, start=1):
                self._session.execute(
                    update(ShotModel)
                    .where(ShotModel.id == shot_id, ShotModel.scene_id == scene_id)
                    .values(order_index=order_index + self._shot_order_shift)
                )

            self._session.execute(
                update(ShotModel)
                .where(
                    ShotModel.scene_id == scene_id,
                    ShotModel.order_index > self._shot_order_shift,
                )
                .values(order_index=ShotModel.order_index - self._shot_order_shift)
            )

            self._session.commit()
            return self.list_shots(scene_id)
        except Exception:
            self._session.rollback()
            raise

    def _lock_scene(self, scene_id: UUID) -> ScreenplaySceneModel | None:
        stmt = (
            select(ScreenplaySceneModel)
            .where(ScreenplaySceneModel.id == scene_id)
            .with_for_update()
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def _count_shots(self, scene_id: UUID) -> int:
        stmt = select(func.count(ShotModel.id)).where(ShotModel.scene_id == scene_id)
        count = self._session.execute(stmt).scalar_one()
        return int(count)

    def _shift_shot_order_down(self, scene_id: UUID, deleted_order_index: int) -> None:
        self._session.execute(
            update(ShotModel)
            .where(ShotModel.scene_id == scene_id, ShotModel.order_index > deleted_order_index)
            .values(order_index=ShotModel.order_index + self._shot_order_shift)
        )
        self._session.execute(
            update(ShotModel)
            .where(
                ShotModel.scene_id == scene_id,
                ShotModel.order_index > deleted_order_index + self._shot_order_shift,
            )
            .values(order_index=ShotModel.order_index - self._shot_order_shift - 1)
        )

    def _to_domain(self, model: ShotModel) -> Shot:
        return Shot(
            id=model.id,
            scene_id=model.scene_id,
            order_index=model.order_index,
            title=model.title,
            description=model.description,
            camera_framing=model.camera_framing,
            camera_movement=model.camera_movement,
            mood=model.mood,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
