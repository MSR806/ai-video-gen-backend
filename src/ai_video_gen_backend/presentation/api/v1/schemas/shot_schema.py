from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from ai_video_gen_backend.domain.shot import (
    Shot,
    ShotCreateInput,
    ShotReorderInput,
    ShotUpdateInput,
)
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class ShotResponse(StrictSchema):
    id: UUID
    scene_id: UUID = Field(alias='sceneId')
    collection_id: UUID | None = Field(default=None, alias='collectionId')
    order_index: int = Field(alias='orderIndex')
    title: str
    description: str
    camera_framing: str = Field(alias='cameraFraming')
    camera_movement: str = Field(alias='cameraMovement')
    mood: str
    created_at: datetime | None = Field(default=None, alias='createdAt')
    updated_at: datetime | None = Field(default=None, alias='updatedAt')

    @classmethod
    def from_domain(cls, shot: Shot) -> ShotResponse:
        return cls(
            id=shot.id,
            scene_id=shot.scene_id,
            collection_id=shot.collection_id,
            order_index=shot.order_index,
            title=shot.title,
            description=shot.description,
            camera_framing=shot.camera_framing,
            camera_movement=shot.camera_movement,
            mood=shot.mood,
            created_at=shot.created_at,
            updated_at=shot.updated_at,
        )


class CreateShotRequest(StrictSchema):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    camera_framing: str = Field(alias='cameraFraming', min_length=1)
    camera_movement: str = Field(alias='cameraMovement', min_length=1)
    mood: str = Field(min_length=1)

    def to_domain(self) -> ShotCreateInput:
        return ShotCreateInput(
            title=self.title,
            description=self.description,
            camera_framing=self.camera_framing,
            camera_movement=self.camera_movement,
            mood=self.mood,
        )


class UpdateShotRequest(StrictSchema):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    camera_framing: str | None = Field(default=None, alias='cameraFraming', min_length=1)
    camera_movement: str | None = Field(default=None, alias='cameraMovement', min_length=1)
    mood: str | None = Field(default=None, min_length=1)

    @model_validator(mode='after')
    def validate_payload(self) -> UpdateShotRequest:
        if len(self.model_fields_set) == 0:
            raise ValueError('at least one field must be provided')

        for field_name in (
            'title',
            'description',
            'camera_framing',
            'camera_movement',
            'mood',
        ):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f'{field_name} must be a string')

        return self

    def to_domain(self) -> ShotUpdateInput:
        return ShotUpdateInput(
            title=self.title,
            description=self.description,
            camera_framing=self.camera_framing,
            camera_movement=self.camera_movement,
            mood=self.mood,
        )


class ReorderShotsRequest(StrictSchema):
    shot_ids: list[UUID] = Field(alias='shotIds', min_length=1)

    @model_validator(mode='after')
    def validate_shot_ids(self) -> ReorderShotsRequest:
        if len(set(self.shot_ids)) != len(self.shot_ids):
            raise ValueError('shotIds must contain unique shot ids')
        return self

    def to_domain(self) -> ShotReorderInput:
        return ShotReorderInput(shot_ids=list(self.shot_ids))
