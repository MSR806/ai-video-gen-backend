from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from ai_video_gen_backend.domain.screenplay import (
    Screenplay,
    ScreenplayCreateInput,
    ScreenplayScene,
    ScreenplaySceneCreateInput,
    ScreenplaySceneUpdateInput,
    canonicalize_scene_xml,
)
from ai_video_gen_backend.infrastructure.db.models import ScreenplayModel, ScreenplaySceneModel


class ScreenplaySqlRepository:
    # Temporary offset used when reindexing scenes in bulk.
    #
    # Why this exists:
    # - We enforce unique (screenplay_id, order_index).
    # - During insert/delete/reorder, direct in-place updates can collide with
    #   existing order_index values inside the same transaction.
    # - We first move affected rows into a high temporary range (+shift), then
    #   move them back into the final contiguous range.
    #
    # This two-phase approach avoids transient uniqueness violations.
    _scene_order_shift = 1000000

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_screenplay_by_project_id(self, project_id: UUID) -> Screenplay | None:
        stmt = (
            select(ScreenplayModel)
            .where(ScreenplayModel.project_id == project_id)
            .options(selectinload(ScreenplayModel.scenes).selectinload(ScreenplaySceneModel.shots))
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    def create_screenplay(self, project_id: UUID, payload: ScreenplayCreateInput) -> Screenplay:
        try:
            model = ScreenplayModel(project_id=project_id, title=payload.title)
            self._session.add(model)
            self._session.commit()
            return self._get_screenplay_by_id(model.id)
        except Exception:
            self._session.rollback()
            raise

    def update_screenplay_title(self, screenplay_id: UUID, title: str) -> Screenplay | None:
        try:
            stmt = select(ScreenplayModel).where(ScreenplayModel.id == screenplay_id)
            model = self._session.execute(stmt).scalar_one_or_none()
            if model is None:
                return None

            model.title = title
            self._session.commit()
            return self._get_screenplay_by_id(screenplay_id)
        except Exception:
            self._session.rollback()
            raise

    def create_screenplay_scene(
        self,
        screenplay_id: UUID,
        payload: ScreenplaySceneCreateInput,
    ) -> Screenplay | None:
        try:
            screenplay = self._lock_screenplay(screenplay_id)
            if screenplay is None:
                return None

            scene_count = self._count_scenes(screenplay_id)
            insert_position = self._normalize_position(payload.position, scene_count + 1)
            self._shift_scene_order_up(screenplay_id, insert_position)

            self._session.add(
                ScreenplaySceneModel(
                    id=uuid4(),
                    screenplay_id=screenplay_id,
                    order_index=insert_position,
                    content_xml=self._normalize_content(payload.content),
                )
            )
            self._session.commit()
            return self._get_screenplay_by_id(screenplay_id)
        except Exception:
            self._session.rollback()
            raise

    def update_screenplay_scene(
        self,
        screenplay_id: UUID,
        scene_id: UUID,
        payload: ScreenplaySceneUpdateInput,
    ) -> ScreenplayScene | None:
        try:
            stmt = select(ScreenplaySceneModel).where(
                ScreenplaySceneModel.id == scene_id,
                ScreenplaySceneModel.screenplay_id == screenplay_id,
            )
            model = self._session.execute(stmt).scalar_one_or_none()
            if model is None:
                return None

            model.content_xml = self._normalize_content(payload.content)
            self._session.commit()
            self._session.refresh(model)
            return self._to_scene_domain(model)
        except Exception:
            self._session.rollback()
            raise

    def delete_screenplay_scene(self, screenplay_id: UUID, scene_id: UUID) -> Screenplay | None:
        try:
            screenplay = self._lock_screenplay(screenplay_id)
            if screenplay is None:
                return None

            stmt = select(ScreenplaySceneModel).where(
                ScreenplaySceneModel.id == scene_id,
                ScreenplaySceneModel.screenplay_id == screenplay_id,
            )
            model = self._session.execute(stmt).scalar_one_or_none()
            if model is None:
                return None

            deleted_order_index = model.order_index
            self._session.delete(model)
            self._session.flush()

            self._shift_scene_order_down(screenplay_id, deleted_order_index)

            self._session.commit()
            return self._get_screenplay_by_id(screenplay_id)
        except Exception:
            self._session.rollback()
            raise

    def reorder_screenplay_scenes(
        self, screenplay_id: UUID, scene_ids: list[UUID]
    ) -> Screenplay | None:
        try:
            screenplay = self._lock_screenplay(screenplay_id)
            if screenplay is None:
                return None

            existing_stmt = (
                select(ScreenplaySceneModel.id)
                .where(ScreenplaySceneModel.screenplay_id == screenplay_id)
                .order_by(ScreenplaySceneModel.order_index.asc())
            )
            existing_ids = list(self._session.execute(existing_stmt).scalars().all())

            if len(existing_ids) != len(scene_ids):
                return None

            existing_id_set = set(existing_ids)
            incoming_id_set = set(scene_ids)
            if existing_id_set != incoming_id_set:
                return None

            for order_index, scene_id in enumerate(scene_ids, start=1):
                self._session.execute(
                    update(ScreenplaySceneModel)
                    .where(
                        ScreenplaySceneModel.id == scene_id,
                        ScreenplaySceneModel.screenplay_id == screenplay_id,
                    )
                    .values(order_index=order_index + self._scene_order_shift)
                )

            self._session.execute(
                update(ScreenplaySceneModel)
                .where(
                    ScreenplaySceneModel.screenplay_id == screenplay_id,
                    ScreenplaySceneModel.order_index > self._scene_order_shift,
                )
                .values(order_index=ScreenplaySceneModel.order_index - self._scene_order_shift)
            )

            self._session.commit()
            return self._get_screenplay_by_id(screenplay_id)
        except Exception:
            self._session.rollback()
            raise

    def _lock_screenplay(self, screenplay_id: UUID) -> ScreenplayModel | None:
        stmt = select(ScreenplayModel).where(ScreenplayModel.id == screenplay_id).with_for_update()
        return self._session.execute(stmt).scalar_one_or_none()

    def _count_scenes(self, screenplay_id: UUID) -> int:
        stmt = select(func.count(ScreenplaySceneModel.id)).where(
            ScreenplaySceneModel.screenplay_id == screenplay_id
        )
        count = self._session.execute(stmt).scalar_one()
        return int(count)

    def _normalize_position(self, position: int | None, max_position: int) -> int:
        if position is None:
            return max_position
        return max(1, min(position, max_position))

    def _shift_scene_order_up(self, screenplay_id: UUID, from_order_index: int) -> None:
        self._session.execute(
            update(ScreenplaySceneModel)
            .where(
                ScreenplaySceneModel.screenplay_id == screenplay_id,
                ScreenplaySceneModel.order_index >= from_order_index,
            )
            .values(order_index=ScreenplaySceneModel.order_index + self._scene_order_shift)
        )
        self._session.execute(
            update(ScreenplaySceneModel)
            .where(
                ScreenplaySceneModel.screenplay_id == screenplay_id,
                ScreenplaySceneModel.order_index >= from_order_index + self._scene_order_shift,
            )
            .values(order_index=ScreenplaySceneModel.order_index - self._scene_order_shift + 1)
        )

    def _shift_scene_order_down(self, screenplay_id: UUID, deleted_order_index: int) -> None:
        self._session.execute(
            update(ScreenplaySceneModel)
            .where(
                ScreenplaySceneModel.screenplay_id == screenplay_id,
                ScreenplaySceneModel.order_index > deleted_order_index,
            )
            .values(order_index=ScreenplaySceneModel.order_index + self._scene_order_shift)
        )
        self._session.execute(
            update(ScreenplaySceneModel)
            .where(
                ScreenplaySceneModel.screenplay_id == screenplay_id,
                ScreenplaySceneModel.order_index > deleted_order_index + self._scene_order_shift,
            )
            .values(order_index=ScreenplaySceneModel.order_index - self._scene_order_shift - 1)
        )

    def _normalize_content(self, content: str) -> str:
        return canonicalize_scene_xml(content)

    def _get_screenplay_by_id(self, screenplay_id: UUID) -> Screenplay:
        stmt = (
            select(ScreenplayModel)
            .where(ScreenplayModel.id == screenplay_id)
            .options(selectinload(ScreenplayModel.scenes).selectinload(ScreenplaySceneModel.shots))
        )
        model = self._session.execute(stmt).scalar_one()
        return self._to_domain(model)

    def _to_domain(self, model: ScreenplayModel) -> Screenplay:
        scenes = [self._to_scene_domain(scene) for scene in model.scenes]
        return Screenplay(
            id=model.id,
            project_id=model.project_id,
            title=model.title,
            scenes=scenes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_scene_domain(self, model: ScreenplaySceneModel) -> ScreenplayScene:
        return ScreenplayScene(
            id=model.id,
            screenplay_id=model.screenplay_id,
            order_index=model.order_index,
            content=self._normalize_content(model.content_xml),
            shot_count=len(model.shots),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
