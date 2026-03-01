from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.project import GetProjectByIdUseCase
from ai_video_gen_backend.application.scene import (
    CreateSceneUseCase,
    DeleteSceneUseCase,
    GetProjectScenesUseCase,
    UpdateSceneUseCase,
)
from ai_video_gen_backend.infrastructure.repositories import (
    ProjectSqlRepository,
    SceneSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import get_db_session
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import (
    CreateSceneRequest,
    SceneResponse,
    SceneSyncResponse,
    SceneUpdateRequest,
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


@router.post('/projects/{project_id}/scenes', response_model=SceneSyncResponse, status_code=201)
def create_project_scene(
    project_id: UUID,
    request: CreateSceneRequest,
    session: Session = Depends(get_db_session),
) -> SceneSyncResponse:
    project_use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    if project_use_case.execute(project_id) is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')

    create_use_case = CreateSceneUseCase(SceneSqlRepository(session))
    scenes = create_use_case.execute(project_id=project_id, payload=request.to_domain())

    return SceneSyncResponse(
        success=True, scenes=[SceneResponse.from_domain(scene) for scene in scenes]
    )


@router.patch('/projects/{project_id}/scenes/{scene_id}', response_model=SceneResponse)
def update_project_scene(
    project_id: UUID,
    scene_id: UUID,
    request: SceneUpdateRequest,
    session: Session = Depends(get_db_session),
) -> SceneResponse:
    project_use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    if project_use_case.execute(project_id) is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')

    update_use_case = UpdateSceneUseCase(SceneSqlRepository(session))
    scene = update_use_case.execute(
        project_id=project_id, scene_id=scene_id, payload=request.to_domain()
    )
    if scene is None:
        raise ApiError(status_code=404, code='scene_not_found', message='Scene not found')

    return SceneResponse.from_domain(scene)


@router.delete('/projects/{project_id}/scenes/{scene_id}', response_model=SceneSyncResponse)
def delete_project_scene(
    project_id: UUID,
    scene_id: UUID,
    session: Session = Depends(get_db_session),
) -> SceneSyncResponse:
    project_use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    if project_use_case.execute(project_id) is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')

    delete_use_case = DeleteSceneUseCase(SceneSqlRepository(session))
    scenes = delete_use_case.execute(project_id=project_id, scene_id=scene_id)
    if scenes is None:
        raise ApiError(status_code=404, code='scene_not_found', message='Scene not found')

    return SceneSyncResponse(
        success=True, scenes=[SceneResponse.from_domain(scene) for scene in scenes]
    )
