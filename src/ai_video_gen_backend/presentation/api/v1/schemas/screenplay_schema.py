from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ai_video_gen_backend.domain.screenplay import (
    SceneXmlValidationError,
    Screenplay,
    ScreenplayCreateInput,
    ScreenplayReorderScenesInput,
    ScreenplayScene,
    ScreenplaySceneCreateInput,
    ScreenplaySceneUpdateInput,
    canonicalize_scene_xml,
)
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class ScreenplaySceneResponse(StrictSchema):
    id: UUID
    screenplay_id: UUID = Field(alias='screenplayId')
    order_index: int = Field(alias='orderIndex')
    content: str
    created_at: datetime | None = Field(default=None, alias='createdAt')
    updated_at: datetime | None = Field(default=None, alias='updatedAt')

    @classmethod
    def from_domain(cls, scene: ScreenplayScene) -> ScreenplaySceneResponse:
        return cls(
            id=scene.id,
            screenplay_id=scene.screenplay_id,
            order_index=scene.order_index,
            content=scene.content,
            created_at=scene.created_at,
            updated_at=scene.updated_at,
        )


class ScreenplayResponse(StrictSchema):
    id: UUID
    project_id: UUID = Field(alias='projectId')
    title: str
    scenes: list[ScreenplaySceneResponse]
    created_at: datetime | None = Field(default=None, alias='createdAt')
    updated_at: datetime | None = Field(default=None, alias='updatedAt')

    @classmethod
    def from_domain(cls, screenplay: Screenplay) -> ScreenplayResponse:
        return cls(
            id=screenplay.id,
            project_id=screenplay.project_id,
            title=screenplay.title,
            scenes=[ScreenplaySceneResponse.from_domain(scene) for scene in screenplay.scenes],
            created_at=screenplay.created_at,
            updated_at=screenplay.updated_at,
        )


class CreateScreenplayRequest(StrictSchema):
    title: str = Field(min_length=1)

    def to_domain(self) -> ScreenplayCreateInput:
        return ScreenplayCreateInput(title=self.title)


class UpdateScreenplayRequest(StrictSchema):
    title: str | None = None

    @model_validator(mode='after')
    def validate_payload(self) -> UpdateScreenplayRequest:
        if 'title' not in self.model_fields_set:
            raise ValueError('title must be provided')
        if self.title is None:
            raise ValueError('title must be a string')
        if len(self.title) == 0:
            raise ValueError('title must not be empty')
        return self


class CreateScreenplaySceneRequest(StrictSchema):
    position: int | None = None
    content: str

    @field_validator('content')
    @classmethod
    def validate_content(cls, value: str) -> str:
        try:
            return canonicalize_scene_xml(value)
        except SceneXmlValidationError as exc:
            raise ValueError(str(exc)) from exc

    def to_domain(self) -> ScreenplaySceneCreateInput:
        return ScreenplaySceneCreateInput(position=self.position, content=self.content)


class UpdateScreenplaySceneRequest(StrictSchema):
    content: str

    @field_validator('content')
    @classmethod
    def validate_content(cls, value: str) -> str:
        try:
            return canonicalize_scene_xml(value)
        except SceneXmlValidationError as exc:
            raise ValueError(str(exc)) from exc

    def to_domain(self) -> ScreenplaySceneUpdateInput:
        return ScreenplaySceneUpdateInput(content=self.content)


class ReorderScreenplayScenesRequest(StrictSchema):
    scene_ids: list[UUID] = Field(alias='sceneIds', min_length=1)

    @model_validator(mode='after')
    def validate_scene_ids(self) -> ReorderScreenplayScenesRequest:
        if len(set(self.scene_ids)) != len(self.scene_ids):
            raise ValueError('sceneIds must contain unique scene ids')
        return self

    def to_domain(self) -> ScreenplayReorderScenesInput:
        return ScreenplayReorderScenesInput(scene_ids=list(self.scene_ids))
