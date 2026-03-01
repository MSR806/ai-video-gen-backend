from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

ProjectStatus = Literal['draft', 'in-progress', 'completed']


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    name: str
    description: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectCreationPayload:
    name: str
    description: str
    status: ProjectStatus = 'draft'
