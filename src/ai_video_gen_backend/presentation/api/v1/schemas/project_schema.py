from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_video_gen_backend.domain.project import Project
from ai_video_gen_backend.presentation.api.v1.schemas.base import StrictSchema


class ProjectResponse(StrictSchema):
    id: UUID
    name: str
    description: str
    status: Literal['draft', 'in-progress', 'completed']
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')

    @classmethod
    def from_domain(cls, project: Project) -> ProjectResponse:
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class CreateProjectRequest(StrictSchema):
    name: str
    description: str
    status: Literal['draft', 'in-progress', 'completed'] = 'draft'
