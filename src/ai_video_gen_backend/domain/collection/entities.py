from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Collection:
    id: UUID
    project_id: UUID
    name: str
    tag: str
    description: str
    created_at: datetime
    updated_at: datetime
