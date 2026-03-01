from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.collection import GetProjectCollectionsUseCase
from ai_video_gen_backend.application.project import GetAllProjectsUseCase, GetProjectByIdUseCase
from ai_video_gen_backend.infrastructure.repositories import (
    CollectionSqlRepository,
    ProjectSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import get_db_session
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import CollectionResponse, ProjectResponse

router = APIRouter(tags=['projects'])


@router.get('/projects', response_model=list[ProjectResponse])
def get_projects(session: Session = Depends(get_db_session)) -> list[ProjectResponse]:
    use_case = GetAllProjectsUseCase(ProjectSqlRepository(session))
    return [ProjectResponse.from_domain(project) for project in use_case.execute()]


@router.get('/projects/{project_id}', response_model=ProjectResponse)
def get_project(project_id: UUID, session: Session = Depends(get_db_session)) -> ProjectResponse:
    use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    project = use_case.execute(project_id)
    if project is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')
    return ProjectResponse.from_domain(project)


@router.get('/projects/{project_id}/collections', response_model=list[CollectionResponse])
def get_project_collections(
    project_id: UUID,
    session: Session = Depends(get_db_session),
) -> list[CollectionResponse]:
    project_use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    if project_use_case.execute(project_id) is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')

    collections_use_case = GetProjectCollectionsUseCase(CollectionSqlRepository(session))
    return [
        CollectionResponse.from_domain(collection)
        for collection in collections_use_case.execute(project_id)
    ]
