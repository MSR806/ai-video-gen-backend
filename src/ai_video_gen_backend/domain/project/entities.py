from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

ProjectStatus = Literal['draft', 'in-progress', 'completed']
DEFAULT_PROJECT_ASPECT_RATIO = '16:9'


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    name: str
    description: str
    style: str | None
    aspect_ratio: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectCreationPayload:
    name: str
    description: str
    style: str | None = None
    aspect_ratio: str = DEFAULT_PROJECT_ASPECT_RATIO
    status: ProjectStatus = 'draft'


@dataclass(frozen=True, slots=True)
class ProjectUpdatePayload:
    name: str | None = None
    description: str | None = None
    style: str | None = None
    aspect_ratio: str | None = None
    update_name: bool = False
    update_description: bool = False
    update_style: bool = False
    update_aspect_ratio: bool = False
