from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.project import GetProjectByIdUseCase
from ai_video_gen_backend.application.scene import GetProjectScenesUseCase, SyncScenesUseCase
from ai_video_gen_backend.domain.scene import SceneInput
from ai_video_gen_backend.infrastructure.repositories import (
    ProjectSqlRepository,
    SceneSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import get_db_session
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import (
    SceneResponse,
    SceneSyncRequest,
    SceneSyncResponse,
)

router = APIRouter(tags=['scenes'])


@router.get('/projects/{project_id}/scenes', response_model=list[SceneResponse])
def get_project_scenes(
    project_id: UUID,
    session: Session = Depends(get_db_session),
) -> list[SceneResponse]:
    project_use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    if project_use_case.execute(project_id) is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')

    scenes_use_case = GetProjectScenesUseCase(SceneSqlRepository(session))
    return [SceneResponse.from_domain(scene) for scene in scenes_use_case.execute(project_id)]


@router.put('/projects/{project_id}/scenes', response_model=SceneSyncResponse)
def sync_project_scenes(
    project_id: UUID,
    request: SceneSyncRequest,
    session: Session = Depends(get_db_session),
) -> SceneSyncResponse:
    project_use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    if project_use_case.execute(project_id) is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')

    scene_inputs = [
        SceneInput(
            id=scene.id,
            name=scene.name,
            scene_number=scene.scene_number,
            content=scene.content,
        )
        for scene in request.scenes
    ]

    sync_use_case = SyncScenesUseCase(SceneSqlRepository(session))
    scenes = sync_use_case.execute(project_id=project_id, scene_inputs=scene_inputs)

    return SceneSyncResponse(
        success=True, scenes=[SceneResponse.from_domain(scene) for scene in scenes]
    )
