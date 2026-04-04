from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from ai_video_gen_backend.domain.chat import ChatStreamCancelledError, ScreenplayChatContext
from ai_video_gen_backend.domain.screenplay import Screenplay, ScreenplayRepositoryPort


@dataclass(slots=True)
class ScreenplayMutationTracker:
    did_mutate: bool = False


@dataclass(frozen=True, slots=True)
class ScreenplayToolsRuntime:
    screenplay_repository: ScreenplayRepositoryPort
    screenplay_context: ScreenplayChatContext
    mutation_tracker: ScreenplayMutationTracker
    is_cancelled: Callable[[], bool] | None

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled is not None and self.is_cancelled():
            raise ChatStreamCancelledError('Streaming chat request was cancelled')

    def get_screenplay(self) -> Screenplay | dict[str, object]:
        self.raise_if_cancelled()
        screenplay = self.screenplay_repository.get_screenplay_by_project_id(
            self.screenplay_context.project_id
        )
        if screenplay is None:
            return {
                'status': 'error',
                'code': 'screenplay_not_found',
                'message': 'Screenplay not found',
            }
        if screenplay.id != self.screenplay_context.screenplay_id:
            return {
                'status': 'error',
                'code': 'screenplay_mismatch',
                'message': 'screenplayId does not belong to projectId',
            }
        return screenplay

    def resolve_scene_id(self, id: str | None) -> tuple[UUID | None, dict[str, object] | None]:
        if id is None:
            if self.screenplay_context.active_scene_id is None:
                return None, {
                    'status': 'error',
                    'code': 'missing_scene_id',
                    'message': 'sceneId is required when no activeSceneId is available',
                }
            return self.screenplay_context.active_scene_id, None

        try:
            return UUID(id), None
        except ValueError:
            return None, {
                'status': 'error',
                'code': 'invalid_scene_id',
                'message': 'sceneId must be a valid UUID string',
            }
