from __future__ import annotations

from uuid import UUID

from ai_video_gen_backend.domain.screenplay import (
    Screenplay,
    ScreenplayRepositoryPort,
    ScreenplaySceneCreateInput,
)


class CreateScreenplaySceneUseCase:
    def __init__(self, screenplay_repository: ScreenplayRepositoryPort) -> None:
        self._screenplay_repository = screenplay_repository

    def execute(
        self, screenplay_id: UUID, payload: ScreenplaySceneCreateInput
    ) -> Screenplay | None:
        return self._screenplay_repository.create_screenplay_scene(screenplay_id, payload)
