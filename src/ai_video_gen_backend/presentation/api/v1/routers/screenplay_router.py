from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.project import GetProjectByIdUseCase
from ai_video_gen_backend.application.screenplay import (
    CreateScreenplaySceneUseCase,
    CreateScreenplayUseCase,
    DeleteScreenplaySceneUseCase,
    GetProjectScreenplayUseCase,
    ReorderScreenplayScenesUseCase,
    UpdateScreenplaySceneUseCase,
    UpdateScreenplayTitleUseCase,
)
from ai_video_gen_backend.infrastructure.repositories import (
    ProjectSqlRepository,
    ScreenplaySqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import get_db_session
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import (
    CreateScreenplayRequest,
    CreateScreenplaySceneRequest,
    ReorderScreenplayScenesRequest,
    ScreenplayResponse,
    ScreenplaySceneResponse,
    UpdateScreenplayRequest,
    UpdateScreenplaySceneRequest,
)

router = APIRouter(tags=['screenplays'])


def _require_project(project_id: UUID, session: Session) -> None:
    project_use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    if project_use_case.execute(project_id) is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')


@router.get('/projects/{project_id}/screenplays', response_model=ScreenplayResponse | None)
def get_project_screenplay(
    project_id: UUID,
    session: Session = Depends(get_db_session),
) -> ScreenplayResponse | None:
    _require_project(project_id, session)

    use_case = GetProjectScreenplayUseCase(ScreenplaySqlRepository(session))
    screenplay = use_case.execute(project_id)
    if screenplay is None:
        return None

    return ScreenplayResponse.from_domain(screenplay)


@router.post(
    '/projects/{project_id}/screenplays', response_model=ScreenplayResponse, status_code=201
)
def create_project_screenplay(
    project_id: UUID,
    request: CreateScreenplayRequest,
    session: Session = Depends(get_db_session),
) -> ScreenplayResponse:
    _require_project(project_id, session)

    repository = ScreenplaySqlRepository(session)
    get_use_case = GetProjectScreenplayUseCase(repository)
    if get_use_case.execute(project_id) is not None:
        raise ApiError(
            status_code=409,
            code='screenplay_already_exists',
            message='A screenplay already exists for this project',
        )

    create_use_case = CreateScreenplayUseCase(repository)
    try:
        screenplay = create_use_case.execute(project_id=project_id, payload=request.to_domain())
    except IntegrityError as exc:
        raise ApiError(
            status_code=409,
            code='screenplay_already_exists',
            message='A screenplay already exists for this project',
        ) from exc

    return ScreenplayResponse.from_domain(screenplay)


@router.patch('/projects/{project_id}/screenplays', response_model=ScreenplayResponse)
def update_project_screenplay(
    project_id: UUID,
    request: UpdateScreenplayRequest,
    session: Session = Depends(get_db_session),
) -> ScreenplayResponse:
    _require_project(project_id, session)

    repository = ScreenplaySqlRepository(session)
    get_use_case = GetProjectScreenplayUseCase(repository)
    screenplay = get_use_case.execute(project_id)
    if screenplay is None:
        raise ApiError(status_code=404, code='screenplay_not_found', message='Screenplay not found')

    if request.title is None:
        raise ApiError(status_code=422, code='validation_error', message='title must be a string')

    update_use_case = UpdateScreenplayTitleUseCase(repository)
    updated = update_use_case.execute(screenplay.id, request.title)
    if updated is None:
        raise ApiError(status_code=404, code='screenplay_not_found', message='Screenplay not found')

    return ScreenplayResponse.from_domain(updated)


@router.post(
    '/projects/{project_id}/screenplays/scenes', response_model=ScreenplayResponse, status_code=201
)
def create_screenplay_scene(
    project_id: UUID,
    request: CreateScreenplaySceneRequest,
    session: Session = Depends(get_db_session),
) -> ScreenplayResponse:
    _require_project(project_id, session)

    repository = ScreenplaySqlRepository(session)
    get_use_case = GetProjectScreenplayUseCase(repository)
    screenplay = get_use_case.execute(project_id)
    if screenplay is None:
        raise ApiError(status_code=404, code='screenplay_not_found', message='Screenplay not found')

    create_use_case = CreateScreenplaySceneUseCase(repository)
    updated = create_use_case.execute(screenplay_id=screenplay.id, payload=request.to_domain())
    if updated is None:
        raise ApiError(status_code=404, code='screenplay_not_found', message='Screenplay not found')

    return ScreenplayResponse.from_domain(updated)


@router.patch(
    '/projects/{project_id}/screenplays/scenes/{scene_id}',
    response_model=ScreenplaySceneResponse,
)
def update_screenplay_scene(
    project_id: UUID,
    scene_id: UUID,
    request: UpdateScreenplaySceneRequest,
    session: Session = Depends(get_db_session),
) -> ScreenplaySceneResponse:
    _require_project(project_id, session)

    repository = ScreenplaySqlRepository(session)
    get_use_case = GetProjectScreenplayUseCase(repository)
    screenplay = get_use_case.execute(project_id)
    if screenplay is None:
        raise ApiError(status_code=404, code='screenplay_not_found', message='Screenplay not found')

    update_use_case = UpdateScreenplaySceneUseCase(repository)
    scene = update_use_case.execute(
        screenplay_id=screenplay.id,
        scene_id=scene_id,
        payload=request.to_domain(),
    )
    if scene is None:
        raise ApiError(
            status_code=404,
            code='screenplay_scene_not_found',
            message='Screenplay scene not found',
        )

    return ScreenplaySceneResponse.from_domain(scene)


@router.delete(
    '/projects/{project_id}/screenplays/scenes/{scene_id}', response_model=ScreenplayResponse
)
def delete_screenplay_scene(
    project_id: UUID,
    scene_id: UUID,
    session: Session = Depends(get_db_session),
) -> ScreenplayResponse:
    _require_project(project_id, session)

    repository = ScreenplaySqlRepository(session)
    get_use_case = GetProjectScreenplayUseCase(repository)
    screenplay = get_use_case.execute(project_id)
    if screenplay is None:
        raise ApiError(status_code=404, code='screenplay_not_found', message='Screenplay not found')

    delete_use_case = DeleteScreenplaySceneUseCase(repository)
    updated = delete_use_case.execute(screenplay_id=screenplay.id, scene_id=scene_id)
    if updated is None:
        raise ApiError(
            status_code=404,
            code='screenplay_scene_not_found',
            message='Screenplay scene not found',
        )

    return ScreenplayResponse.from_domain(updated)


@router.post('/projects/{project_id}/screenplays/scenes/reorder', response_model=ScreenplayResponse)
def reorder_screenplay_scenes(
    project_id: UUID,
    request: ReorderScreenplayScenesRequest,
    session: Session = Depends(get_db_session),
) -> ScreenplayResponse:
    _require_project(project_id, session)

    repository = ScreenplaySqlRepository(session)
    get_use_case = GetProjectScreenplayUseCase(repository)
    screenplay = get_use_case.execute(project_id)
    if screenplay is None:
        raise ApiError(status_code=404, code='screenplay_not_found', message='Screenplay not found')

    reorder_use_case = ReorderScreenplayScenesUseCase(repository)
    reordered = reorder_use_case.execute(screenplay.id, request.to_domain().scene_ids)
    if reordered is None:
        raise ApiError(
            status_code=400,
            code='invalid_scene_order',
            message='sceneIds must include each screenplay scene id exactly once',
        )

    return ScreenplayResponse.from_domain(reordered)
