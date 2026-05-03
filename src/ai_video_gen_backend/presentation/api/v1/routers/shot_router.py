from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.project import GetProjectByIdUseCase
from ai_video_gen_backend.application.screenplay import GetProjectScreenplayUseCase
from ai_video_gen_backend.application.shot import (
    CreateShotUseCase,
    DeleteShotUseCase,
    EnsureShotVisualCollectionUseCase,
    GenerateShotsUseCase,
    GenerateShotVisualsUseCase,
    ListShotsUseCase,
    ReorderShotsUseCase,
    UpdateShotUseCase,
)
from ai_video_gen_backend.application.shot import (
    GenerateShotVisualsRequest as GenerateShotVisualsUseCaseRequest,
)
from ai_video_gen_backend.infrastructure.repositories import (
    ProjectSqlRepository,
    ScreenplaySqlRepository,
    ShotSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import (
    get_db_session,
    get_ensure_shot_visual_collection_use_case,
    get_generate_shot_visuals_use_case,
    get_generate_shots_use_case,
)
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import (
    CollectionResponse,
    CreateShotRequest,
    GenerateShotVisualsRequest,
    ReorderShotsRequest,
    ShotResponse,
    ShotVisualGenerationResponse,
    UpdateShotRequest,
)

router = APIRouter(tags=['shots'])


def _require_project(project_id: UUID, session: Session) -> None:
    project_use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    if project_use_case.execute(project_id) is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')


def _require_project_scene(project_id: UUID, scene_id: UUID, session: Session) -> None:
    _require_project(project_id, session)
    screenplay = GetProjectScreenplayUseCase(ScreenplaySqlRepository(session)).execute(project_id)
    if screenplay is None:
        raise ApiError(status_code=404, code='screenplay_not_found', message='Screenplay not found')

    if not any(scene.id == scene_id for scene in screenplay.scenes):
        raise ApiError(
            status_code=404,
            code='screenplay_scene_not_found',
            message='Screenplay scene not found',
        )


@router.get(
    '/projects/{project_id}/screenplays/scenes/{scene_id}/shots', response_model=list[ShotResponse]
)
def list_scene_shots(
    project_id: UUID,
    scene_id: UUID,
    session: Session = Depends(get_db_session),
) -> list[ShotResponse]:
    _require_project_scene(project_id, scene_id, session)

    shots = ListShotsUseCase(ShotSqlRepository(session)).execute(scene_id)
    return [ShotResponse.from_domain(shot) for shot in shots]


@router.post(
    '/projects/{project_id}/screenplays/scenes/{scene_id}/shots',
    response_model=ShotResponse,
    status_code=201,
)
def create_scene_shot(
    project_id: UUID,
    scene_id: UUID,
    request: CreateShotRequest,
    session: Session = Depends(get_db_session),
) -> ShotResponse:
    _require_project_scene(project_id, scene_id, session)

    shot = CreateShotUseCase(ShotSqlRepository(session)).execute(scene_id, request.to_domain())
    if shot is None:
        raise ApiError(
            status_code=404,
            code='screenplay_scene_not_found',
            message='Screenplay scene not found',
        )

    return ShotResponse.from_domain(shot)


@router.patch(
    '/projects/{project_id}/screenplays/scenes/{scene_id}/shots/{shot_id}',
    response_model=ShotResponse,
)
def update_scene_shot(
    project_id: UUID,
    scene_id: UUID,
    shot_id: UUID,
    request: UpdateShotRequest,
    session: Session = Depends(get_db_session),
) -> ShotResponse:
    _require_project_scene(project_id, scene_id, session)

    shot = UpdateShotUseCase(ShotSqlRepository(session)).execute(
        scene_id, shot_id, request.to_domain()
    )
    if shot is None:
        raise ApiError(status_code=404, code='shot_not_found', message='Shot not found')

    return ShotResponse.from_domain(shot)


@router.delete(
    '/projects/{project_id}/screenplays/scenes/{scene_id}/shots/{shot_id}', status_code=204
)
def delete_scene_shot(
    project_id: UUID,
    scene_id: UUID,
    shot_id: UUID,
    session: Session = Depends(get_db_session),
) -> Response:
    _require_project_scene(project_id, scene_id, session)

    deleted = DeleteShotUseCase(ShotSqlRepository(session)).execute(scene_id, shot_id)
    if not deleted:
        raise ApiError(status_code=404, code='shot_not_found', message='Shot not found')

    return Response(status_code=204)


@router.post(
    '/projects/{project_id}/screenplays/scenes/{scene_id}/shots/reorder',
    response_model=list[ShotResponse],
)
def reorder_scene_shots(
    project_id: UUID,
    scene_id: UUID,
    request: ReorderShotsRequest,
    session: Session = Depends(get_db_session),
) -> list[ShotResponse]:
    _require_project_scene(project_id, scene_id, session)

    reordered = ReorderShotsUseCase(ShotSqlRepository(session)).execute(
        scene_id, request.to_domain().shot_ids
    )
    if reordered is None:
        raise ApiError(
            status_code=400,
            code='invalid_shot_order',
            message='shotIds must include each scene shot id exactly once',
        )

    return [ShotResponse.from_domain(shot) for shot in reordered]


@router.post(
    '/projects/{project_id}/screenplays/scenes/{scene_id}/shots/generate',
    response_model=list[ShotResponse],
)
def generate_scene_shots(
    project_id: UUID,
    scene_id: UUID,
    generate_shots_use_case: GenerateShotsUseCase = Depends(get_generate_shots_use_case),
    session: Session = Depends(get_db_session),
) -> list[ShotResponse]:
    _require_project_scene(project_id, scene_id, session)

    generated = generate_shots_use_case.execute(project_id=project_id, scene_id=scene_id)
    if generated is None:
        raise ApiError(
            status_code=404,
            code='screenplay_scene_not_found',
            message='Screenplay scene not found',
        )

    return [ShotResponse.from_domain(shot) for shot in generated]


@router.post(
    '/projects/{project_id}/screenplays/scenes/{scene_id}/shots/{shot_id}/visual-collection',
    response_model=CollectionResponse,
)
def ensure_shot_visual_collection(
    project_id: UUID,
    scene_id: UUID,
    shot_id: UUID,
    use_case: EnsureShotVisualCollectionUseCase = Depends(
        get_ensure_shot_visual_collection_use_case
    ),
    session: Session = Depends(get_db_session),
) -> CollectionResponse:
    _require_project_scene(project_id, scene_id, session)

    collection = use_case.execute(project_id=project_id, scene_id=scene_id, shot_id=shot_id)
    if collection is None:
        raise ApiError(status_code=404, code='shot_not_found', message='Shot not found')

    return CollectionResponse.from_domain(collection)


@router.post(
    '/projects/{project_id}/screenplays/scenes/{scene_id}/shots/generate-visuals',
    response_model=list[ShotVisualGenerationResponse],
    status_code=202,
)
def generate_shot_visuals(
    project_id: UUID,
    scene_id: UUID,
    request: GenerateShotVisualsRequest,
    use_case: GenerateShotVisualsUseCase = Depends(get_generate_shot_visuals_use_case),
) -> list[ShotVisualGenerationResponse]:
    generated = use_case.execute(
        GenerateShotVisualsUseCaseRequest(
            project_id=project_id,
            scene_id=scene_id,
            shot_ids=request.shot_ids,
            model_key=request.model_key,
            operation_key=request.operation_key,
            prompt=request.prompt,
        )
    )
    return [
        ShotVisualGenerationResponse(
            shot_id=result.shot_id,
            collection_id=result.collection_id,
            run_id=result.run_id,
            status=result.status,
            error=result.error,
        )
        for result in generated
    ]
