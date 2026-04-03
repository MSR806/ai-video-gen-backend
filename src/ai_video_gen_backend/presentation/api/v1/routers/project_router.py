from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_video_gen_backend.application.collection import (
    CreateCollectionUseCase,
    GetProjectCollectionsUseCase,
)
from ai_video_gen_backend.application.project import (
    CreateProjectUseCase,
    GetAllProjectsUseCase,
    GetProjectByIdUseCase,
)
from ai_video_gen_backend.domain.collection import CollectionCreationPayload
from ai_video_gen_backend.domain.project import ProjectCreationPayload
from ai_video_gen_backend.infrastructure.repositories import (
    CollectionItemSqlRepository,
    CollectionSqlRepository,
    ProjectSqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import get_db_session
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import (
    CollectionResponse,
    CreateCollectionRequest,
    CreateProjectRequest,
    ProjectResponse,
)

router = APIRouter(tags=['projects'])


@router.get('/projects', response_model=list[ProjectResponse])
def get_projects(session: Session = Depends(get_db_session)) -> list[ProjectResponse]:
    use_case = GetAllProjectsUseCase(ProjectSqlRepository(session))
    return [ProjectResponse.from_domain(project) for project in use_case.execute()]


@router.post('/projects', response_model=ProjectResponse, status_code=201)
def create_project(
    request: CreateProjectRequest,
    session: Session = Depends(get_db_session),
) -> ProjectResponse:
    use_case = CreateProjectUseCase(ProjectSqlRepository(session))
    project = use_case.execute(
        ProjectCreationPayload(
            name=request.name,
            description=request.description,
            status=request.status,
        )
    )
    return ProjectResponse.from_domain(project)


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
    collections = collections_use_case.execute(project_id)
    item_repository = CollectionItemSqlRepository(session)
    thumbnail_urls = item_repository.get_first_item_thumbnail_urls_by_collection_ids(
        [collection.id for collection in collections]
    )
    return [
        CollectionResponse.from_domain(
            collection,
            thumbnail_url=thumbnail_urls.get(collection.id),
        )
        for collection in collections
    ]


@router.post(
    '/projects/{project_id}/collections',
    response_model=CollectionResponse,
    status_code=201,
)
def create_project_collection(
    project_id: UUID,
    request: CreateCollectionRequest,
    session: Session = Depends(get_db_session),
) -> CollectionResponse:
    project_use_case = GetProjectByIdUseCase(ProjectSqlRepository(session))
    if project_use_case.execute(project_id) is None:
        raise ApiError(status_code=404, code='project_not_found', message='Project not found')

    collection_repository = CollectionSqlRepository(session)
    if request.parent_collection_id is not None:
        parent_collection = collection_repository.get_collection_by_id(request.parent_collection_id)
        if parent_collection is None or parent_collection.project_id != project_id:
            raise ApiError(
                status_code=400,
                code='invalid_parent_collection',
                message='Parent collection must exist in the same project',
            )

    use_case = CreateCollectionUseCase(collection_repository)
    collection = use_case.execute(
        CollectionCreationPayload(
            project_id=project_id,
            name=request.name,
            tag=request.tag,
            description=request.description,
            parent_collection_id=request.parent_collection_id,
        )
    )
    return CollectionResponse.from_domain(collection)
