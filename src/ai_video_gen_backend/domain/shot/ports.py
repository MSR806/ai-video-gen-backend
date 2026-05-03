from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import Shot, ShotCreateInput, ShotUpdateInput


class ShotRepositoryPort(Protocol):
    def list_shots(self, scene_id: UUID) -> list[Shot]: ...

    def get_shot(self, scene_id: UUID, shot_id: UUID) -> Shot | None: ...

    def create_shot(self, scene_id: UUID, payload: ShotCreateInput) -> Shot | None: ...

    def update_shot(
        self, scene_id: UUID, shot_id: UUID, payload: ShotUpdateInput
    ) -> Shot | None: ...

    def set_shot_collection(
        self, scene_id: UUID, shot_id: UUID, collection_id: UUID
    ) -> Shot | None: ...

    def delete_shot(self, scene_id: UUID, shot_id: UUID) -> bool: ...

    def reorder_shots(self, scene_id: UUID, shot_ids: list[UUID]) -> list[Shot] | None: ...

    def replace_shots(
        self, scene_id: UUID, payloads: list[ShotCreateInput]
    ) -> list[Shot] | None: ...


class ShotGenerationPort(Protocol):
    def generate_shots(self, scene_content: str) -> list[ShotCreateInput]: ...
