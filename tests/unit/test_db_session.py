from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from ai_video_gen_backend.infrastructure.db import session as db_session


class FakeSession:
    def __init__(self) -> None:
        self.rollback_calls = 0
        self.close_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def __call__(self) -> Session:
        return cast(Session, self._session)


def test_get_engine_and_session_factory_raise_when_not_configured() -> None:
    db_session._ENGINE = None
    db_session._SESSION_FACTORY = None

    with pytest.raises(RuntimeError, match='Database engine is not configured'):
        db_session.get_engine()

    with pytest.raises(RuntimeError, match='Session factory is not configured'):
        db_session.get_session_factory()


def test_configure_engine_sqlite_and_force_reconfigure() -> None:
    db_session._ENGINE = None
    db_session._SESSION_FACTORY = None

    db_session.configure_engine('sqlite+pysqlite:///:memory:')
    first_engine = db_session.get_engine()

    db_session.configure_engine('sqlite+pysqlite:///:memory:')
    assert db_session.get_engine() is first_engine

    db_session.configure_engine('sqlite+pysqlite:///:memory:', force=True)
    second_engine = db_session.get_engine()
    assert second_engine is not first_engine

    with db_session.get_session_factory()() as session:
        result = session.execute(text('PRAGMA foreign_keys')).scalar_one()
        assert result == 1


def test_session_scope_rolls_back_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = FakeSession()
    monkeypatch.setattr(db_session, 'get_session_factory', lambda: FakeSessionFactory(fake_session))

    scope = db_session.session_scope()
    started = next(scope)
    assert isinstance(started, FakeSession)

    with pytest.raises(ValueError, match='boom'):
        scope.throw(ValueError('boom'))

    assert fake_session.rollback_calls == 1
    assert fake_session.close_calls == 1


def test_session_scope_closes_session_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = FakeSession()
    monkeypatch.setattr(db_session, 'get_session_factory', lambda: FakeSessionFactory(fake_session))

    scope = db_session.session_scope()
    started = next(scope)
    assert isinstance(started, FakeSession)

    with pytest.raises(StopIteration):
        next(scope)

    assert fake_session.rollback_calls == 0
    assert fake_session.close_calls == 1
