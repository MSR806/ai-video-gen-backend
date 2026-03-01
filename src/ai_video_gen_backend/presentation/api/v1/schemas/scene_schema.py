from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from ai_video_gen_backend.domain.scene import Scene, SceneCreateInput, SceneUpdateInput
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


class CreateSceneRequest(StrictSchema):
    id: UUID | None = None
    position: int | None = None
    name: str | None = None
    content: dict[str, JsonValue] | None = None

    def to_domain(self) -> SceneCreateInput:
        return SceneCreateInput(
            id=self.id,
            position=self.position,
            name=self.name,
            content=self.content,
        )


class SceneUpdateRequest(StrictSchema):
    name: str | None = None
    content: dict[str, JsonValue] | None = None

    @model_validator(mode='after')
    def validate_patch_payload(self) -> SceneUpdateRequest:
        provided_fields = self.model_fields_set
        if 'name' not in provided_fields and 'content' not in provided_fields:
            raise ValueError('At least one of name or content must be provided')

        if 'name' in provided_fields and self.name is None:
            raise ValueError('name must be a string')

        if 'content' in provided_fields and self.content is None:
            raise ValueError('content must be an object')

        return self

    def to_domain(self) -> SceneUpdateInput:
        return SceneUpdateInput(
            name=self.name,
            content=self.content,
            update_name='name' in self.model_fields_set,
            update_content='content' in self.model_fields_set,
        )


class SceneSyncResponse(StrictSchema):
    success: bool
    scenes: list[SceneResponse]
