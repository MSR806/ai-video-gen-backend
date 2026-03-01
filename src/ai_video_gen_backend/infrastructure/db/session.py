from __future__ import annotations

from collections.abc import Generator
from typing import Protocol

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


class CursorProtocol(Protocol):
    def execute(self, statement: str) -> object: ...

    def close(self) -> None: ...


class DBAPIConnectionProtocol(Protocol):
    def cursor(self) -> CursorProtocol: ...


def configure_engine(database_url: str, force: bool = False) -> None:
    global _ENGINE, _SESSION_FACTORY

    if force and _ENGINE is not None:
        _ENGINE.dispose()
        _ENGINE = None
        _SESSION_FACTORY = None

    if _ENGINE is not None:
        return

    connect_args: dict[str, object] = {}
    if database_url.startswith('sqlite'):
        connect_args['check_same_thread'] = False

    _ENGINE = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    if database_url.startswith('sqlite'):

        @event.listens_for(_ENGINE, 'connect')
        def _set_sqlite_pragma(dbapi_connection: DBAPIConnectionProtocol, _: object) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()

    _SESSION_FACTORY = sessionmaker(
        bind=_ENGINE,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_engine() -> Engine:
    if _ENGINE is None:
        msg = 'Database engine is not configured.'
        raise RuntimeError(msg)
    return _ENGINE


def get_session_factory() -> sessionmaker[Session]:
    if _SESSION_FACTORY is None:
        msg = 'Session factory is not configured.'
        raise RuntimeError(msg)
    return _SESSION_FACTORY


def session_scope() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db_connection(session: Session) -> None:
    session.execute(text('SELECT 1'))
