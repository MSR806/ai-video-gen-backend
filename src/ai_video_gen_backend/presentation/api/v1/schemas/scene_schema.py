from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.scene import Scene
from ai_video_gen_backend.domain.scene.entities import JsonValue
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class SceneResponse(StrictSchema):
    id: UUID
    project_id: UUID = Field(alias='projectId')
    name: str
    scene_number: int = Field(alias='sceneNumber')
    content: dict[str, JsonValue]
    created_at: datetime | None = Field(default=None, alias='createdAt')
    updated_at: datetime | None = Field(default=None, alias='updatedAt')

    @classmethod
    def from_domain(cls, scene: Scene) -> SceneResponse:
        return cls(
            id=scene.id,
            project_id=scene.project_id,
            name=scene.name,
            scene_number=scene.scene_number,
            content=scene.content,
            created_at=scene.created_at,
            updated_at=scene.updated_at,
        )


class SceneInputRequest(StrictSchema):
    id: UUID | None = None
    name: str | None = None
    scene_number: int | None = Field(default=None, alias='sceneNumber')
    content: dict[str, JsonValue] | None = None


class SceneSyncRequest(StrictSchema):
    scenes: list[SceneInputRequest]


class SceneSyncResponse(StrictSchema):
    success: bool
    scenes: list[SceneResponse]
