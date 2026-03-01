from __future__ import annotations

from copy import deepcopy
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.scene import Scene, SceneCreateInput, SceneUpdateInput
from ai_video_gen_backend.infrastructure.db.models import SceneModel


class SceneSqlRepository:
    _scene_number_shift = 1000000

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_scenes_by_project_id(self, project_id: UUID) -> list[Scene]:
        stmt = (
            select(SceneModel)
            .where(SceneModel.project_id == project_id)
            .order_by(SceneModel.scene_number.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(record) for record in records]

    def get_scene_by_id(self, scene_id: UUID) -> Scene | None:
        stmt = select(SceneModel).where(SceneModel.id == scene_id)
        record = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(record) if record is not None else None

    def create_scene(self, project_id: UUID, payload: SceneCreateInput) -> list[Scene]:
        try:
            self._lock_project_scenes(project_id)

            current_count = self._count_project_scenes(project_id)
            insert_position = self._normalize_position(payload.position, current_count + 1)
            self._shift_scene_numbers_up(project_id, from_scene_number=insert_position)

            scene_name = self._normalize_name(payload.name, fallback_scene_number=insert_position)
            scene_content = self._normalize_content(payload.content)

            self._session.add(
                SceneModel(
                    id=payload.id or uuid4(),
                    project_id=project_id,
                    name=scene_name,
                    scene_number=insert_position,
                    content_json=scene_content,
                )
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return self.get_scenes_by_project_id(project_id)

    def update_scene(
        self,
        project_id: UUID,
        scene_id: UUID,
        payload: SceneUpdateInput,
    ) -> Scene | None:
        try:
            stmt = select(SceneModel).where(
                SceneModel.id == scene_id, SceneModel.project_id == project_id
            )
            record = self._session.execute(stmt).scalar_one_or_none()
            if record is None:
                return None

            if payload.update_name:
                record.name = self._normalize_name(
                    payload.name, fallback_scene_number=record.scene_number
                )

            if payload.update_content:
                record.content_json = self._normalize_content(payload.content)

            self._session.commit()
            self._session.refresh(record)
            return self._to_domain(record)
        except Exception:
            self._session.rollback()
            raise

    def delete_scene(self, project_id: UUID, scene_id: UUID) -> list[Scene] | None:
        try:
            self._lock_project_scenes(project_id)

            stmt = select(SceneModel).where(
                SceneModel.id == scene_id, SceneModel.project_id == project_id
            )
            record = self._session.execute(stmt).scalar_one_or_none()
            if record is None:
                return None

            deleted_scene_number = record.scene_number
            self._session.delete(record)
            self._session.flush()

            self._shift_scene_numbers_down(project_id, deleted_scene_number=deleted_scene_number)

            if self._count_project_scenes(project_id) == 0:
                self._session.add(
                    SceneModel(
                        id=uuid4(),
                        project_id=project_id,
                        name='Untitled Scene 1',
                        scene_number=1,
                        content_json=self._empty_content(),
                    )
                )

            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return self.get_scenes_by_project_id(project_id)

    def _lock_project_scenes(self, project_id: UUID) -> None:
        lock_stmt = (
            select(SceneModel.id)
            .where(SceneModel.project_id == project_id)
            .order_by(SceneModel.scene_number.asc())
            .with_for_update()
        )
        self._session.execute(lock_stmt).all()

    def _count_project_scenes(self, project_id: UUID) -> int:
        count_stmt = select(func.count(SceneModel.id)).where(SceneModel.project_id == project_id)
        count_value = self._session.execute(count_stmt).scalar_one()
        return int(count_value)

    def _normalize_position(self, position: int | None, max_position: int) -> int:
        if position is None:
            return max_position
        return max(1, min(position, max_position))

    def _shift_scene_numbers_up(self, project_id: UUID, from_scene_number: int) -> None:
        self._session.execute(
            update(SceneModel)
            .where(
                SceneModel.project_id == project_id,
                SceneModel.scene_number >= from_scene_number,
            )
            .values(scene_number=SceneModel.scene_number + self._scene_number_shift)
        )
        self._session.execute(
            update(SceneModel)
            .where(
                SceneModel.project_id == project_id,
                SceneModel.scene_number >= from_scene_number + self._scene_number_shift,
            )
            .values(scene_number=SceneModel.scene_number - self._scene_number_shift + 1)
        )

    def _shift_scene_numbers_down(self, project_id: UUID, deleted_scene_number: int) -> None:
        self._session.execute(
            update(SceneModel)
            .where(
                SceneModel.project_id == project_id,
                SceneModel.scene_number > deleted_scene_number,
            )
            .values(scene_number=SceneModel.scene_number + self._scene_number_shift)
        )
        self._session.execute(
            update(SceneModel)
            .where(
                SceneModel.project_id == project_id,
                SceneModel.scene_number > deleted_scene_number + self._scene_number_shift,
            )
            .values(scene_number=SceneModel.scene_number - self._scene_number_shift - 1)
        )

    def _normalize_name(self, name: str | None, fallback_scene_number: int) -> str:
        normalized = name.strip() if name else ''
        if len(normalized) > 0:
            return normalized
        return f'Untitled Scene {fallback_scene_number}'

    def _normalize_content(self, content: dict[str, object] | None) -> dict[str, object]:
        return deepcopy(content) if content is not None else self._empty_content()

    def _empty_content(self) -> dict[str, object]:
        return {'text': ''}

    def _to_domain(self, model: SceneModel) -> Scene:
        return Scene(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            scene_number=model.scene_number,
            content=model.content_json,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
