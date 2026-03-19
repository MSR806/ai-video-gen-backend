from __future__ import annotations

import pytest
from sqlalchemy import text

from ai_video_gen_backend.infrastructure.db import session as db_session


def test_get_engine_and_factory_raise_when_not_configured() -> None:
    db_session.configure_engine('sqlite+pysqlite:///:memory:', force=True)
    db_session.get_engine().dispose()
    db_session._ENGINE = None
    db_session._SESSION_FACTORY = None

    with pytest.raises(RuntimeError, match='Database engine is not configured'):
        db_session.get_engine()

    with pytest.raises(RuntimeError, match='Session factory is not configured'):
        db_session.get_session_factory()


def test_configure_engine_sets_sqlite_foreign_keys_pragma() -> None:
    db_session.configure_engine('sqlite+pysqlite:///:memory:', force=True)

    engine = db_session.get_engine()
    with engine.connect() as connection:
        result = connection.execute(text('PRAGMA foreign_keys')).scalar_one()

    assert result == 1


def test_session_scope_rolls_back_on_exception() -> None:
    db_session.configure_engine('sqlite+pysqlite:///:memory:', force=True)
    engine = db_session.get_engine()

    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)'))

    scope = db_session.session_scope()
    session = next(scope)
    session.execute(text("INSERT INTO items (name) VALUES ('temp')"))

    with pytest.raises(ValueError, match='boom'):
        scope.throw(ValueError('boom'))

    verify_scope = db_session.session_scope()
    verify_session = next(verify_scope)
    try:
        count = verify_session.execute(text('SELECT COUNT(*) FROM items')).scalar_one()
    finally:
        verify_scope.close()

    assert count == 0
