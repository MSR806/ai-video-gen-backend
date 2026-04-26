from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import Shot, ShotCreateInput, ShotUpdateInput


class ShotRepositoryPort(Protocol):
    def list_shots(self, scene_id: UUID) -> list[Shot]: ...

    def create_shot(self, scene_id: UUID, payload: ShotCreateInput) -> Shot | None: ...

    def update_shot(
        self, scene_id: UUID, shot_id: UUID, payload: ShotUpdateInput
    ) -> Shot | None: ...

    def delete_shot(self, scene_id: UUID, shot_id: UUID) -> bool: ...

    def reorder_shots(self, scene_id: UUID, shot_ids: list[UUID]) -> list[Shot] | None: ...
