from __future__ import annotations

import asyncio
import importlib
from collections.abc import Generator
from contextlib import AbstractAsyncContextManager

import pytest

langgraph_postgres_checkpointer = importlib.import_module(
    'ai_video_gen_backend.infrastructure.providers.langgraph_postgres_checkpointer'
)


class _FakeCheckpointer:
    def __init__(self) -> None:
        self.setup_calls = 0

    async def setup(self) -> None:
        self.setup_calls += 1


class _FakeContextManager(AbstractAsyncContextManager[_FakeCheckpointer]):
    def __init__(self, checkpointer: _FakeCheckpointer) -> None:
        self.checkpointer = checkpointer
        self.exit_calls = 0

    async def __aenter__(self) -> _FakeCheckpointer:
        return self.checkpointer

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb
        self.exit_calls += 1


@pytest.fixture(autouse=True)
def _reset_checkpointer_state() -> Generator[None, None, None]:
    asyncio.run(langgraph_postgres_checkpointer.close_langgraph_postgres_checkpointer())
    yield
    asyncio.run(langgraph_postgres_checkpointer.close_langgraph_postgres_checkpointer())


def test_get_langgraph_postgres_checkpointer_initializes_and_reuses_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpointer = _FakeCheckpointer()
    context_manager = _FakeContextManager(checkpointer)
    calls: list[str] = []

    def _from_conn_string(connection_string: str) -> _FakeContextManager:
        calls.append(connection_string)
        return context_manager

    monkeypatch.setattr(
        langgraph_postgres_checkpointer.AsyncPostgresSaver,
        'from_conn_string',
        _from_conn_string,
    )

    first = asyncio.run(
        langgraph_postgres_checkpointer.get_langgraph_postgres_checkpointer(
            database_url='postgresql+psycopg://user:pw@localhost:5432/app'
        )
    )
    second = asyncio.run(
        langgraph_postgres_checkpointer.get_langgraph_postgres_checkpointer(
            database_url='postgresql+psycopg://user:pw@localhost:5432/app'
        )
    )

    assert first is checkpointer
    assert second is checkpointer
    assert calls == ['postgresql://user:pw@localhost:5432/app']
    assert checkpointer.setup_calls == 1


def test_get_langgraph_postgres_checkpointer_rejects_non_postgres_url() -> None:
    with pytest.raises(ValueError, match='requires a PostgreSQL database URL'):
        asyncio.run(
            langgraph_postgres_checkpointer.get_langgraph_postgres_checkpointer(
                database_url='sqlite+pysqlite:///tmp/test.db'
            )
        )


def test_get_langgraph_postgres_checkpointer_rejects_url_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpointer = _FakeCheckpointer()
    context_manager = _FakeContextManager(checkpointer)

    monkeypatch.setattr(
        langgraph_postgres_checkpointer.AsyncPostgresSaver,
        'from_conn_string',
        lambda connection_string: context_manager,
    )

    asyncio.run(
        langgraph_postgres_checkpointer.get_langgraph_postgres_checkpointer(
            database_url='postgresql://user:pw@localhost:5432/app_a'
        )
    )

    with pytest.raises(RuntimeError, match='different database URL'):
        asyncio.run(
            langgraph_postgres_checkpointer.get_langgraph_postgres_checkpointer(
                database_url='postgresql://user:pw@localhost:5432/app_b'
            )
        )


def test_close_langgraph_postgres_checkpointer_closes_open_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpointer = _FakeCheckpointer()
    context_manager = _FakeContextManager(checkpointer)

    monkeypatch.setattr(
        langgraph_postgres_checkpointer.AsyncPostgresSaver,
        'from_conn_string',
        lambda connection_string: context_manager,
    )

    asyncio.run(
        langgraph_postgres_checkpointer.get_langgraph_postgres_checkpointer(
            database_url='postgresql://user:pw@localhost:5432/app'
        )
    )
    asyncio.run(langgraph_postgres_checkpointer.close_langgraph_postgres_checkpointer())

    assert context_manager.exit_calls == 1
