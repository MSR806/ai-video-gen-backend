from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.scene import Scene
from ai_video_gen_backend.infrastructure.db.models import SceneModel


class SceneSqlRepository:
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

    def bulk_replace(self, project_id: UUID, scenes: list[Scene]) -> None:
        try:
            self._session.execute(delete(SceneModel).where(SceneModel.project_id == project_id))
            for scene in scenes:
                self._session.add(
                    SceneModel(
                        id=scene.id,
                        project_id=project_id,
                        name=scene.name,
                        scene_number=scene.scene_number,
                        body=scene.body,
                        content_json=scene.content,
                    )
                )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _to_domain(self, model: SceneModel) -> Scene:
        return Scene(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            scene_number=model.scene_number,
            body=model.body,
            content=model.content_json,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
