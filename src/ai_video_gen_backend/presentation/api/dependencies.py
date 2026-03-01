from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from ai_video_gen_backend.infrastructure.db.session import get_session_factory


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
