from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.project import DEFAULT_PROJECT_ASPECT_RATIO, Project
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class ProjectResponse(StrictSchema):
    id: UUID
    name: str
    description: str
    style: str | None = None
    aspect_ratio: str = Field(alias='aspectRatio')
    status: Literal['draft', 'in-progress', 'completed']
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')

    @classmethod
    def from_domain(cls, project: Project) -> ProjectResponse:
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            style=project.style,
            aspect_ratio=project.aspect_ratio,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class CreateProjectRequest(StrictSchema):
    name: str
    description: str
    style: str | None = None
    aspect_ratio: str | None = Field(default=None, alias='aspectRatio')
    status: Literal['draft', 'in-progress', 'completed'] = 'draft'

    def to_domain_aspect_ratio(self) -> str:
        return self.aspect_ratio or DEFAULT_PROJECT_ASPECT_RATIO


class UpdateProjectRequest(StrictSchema):
    name: str | None = None
    description: str | None = None
    style: str | None = None
    aspect_ratio: str | None = Field(default=None, alias='aspectRatio')
