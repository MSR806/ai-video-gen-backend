from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_video_gen_backend.infrastructure.db.session import check_db_connection
from ai_video_gen_backend.presentation.api.dependencies import get_db_session
from ai_video_gen_backend.presentation.api.errors import ApiError

router = APIRouter(prefix='/health', tags=['health'])


@router.get('/live')
def live() -> dict[str, str]:
    return {'status': 'ok'}


@router.get('/ready')
def ready(session: Session = Depends(get_db_session)) -> dict[str, str]:
    try:
        check_db_connection(session)
    except SQLAlchemyError as exc:
        raise ApiError(
            status_code=503,
            code='database_unavailable',
            message='Database is unavailable',
            details={'reason': str(exc.__class__.__name__)},
        ) from exc
    return {'status': 'ready'}
