from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class _AsyncSetupCapableCheckpointer(Protocol):
    async def setup(self) -> None: ...


@dataclass(slots=True)
class _CheckpointerState:
    context_manager: AbstractAsyncContextManager[_AsyncSetupCapableCheckpointer]
    checkpointer: _AsyncSetupCapableCheckpointer
    database_url: str


_state: _CheckpointerState | None = None
_state_lock = asyncio.Lock()


async def get_langgraph_postgres_checkpointer(*, database_url: str) -> object:
    global _state

    if _state is not None:
        _raise_if_database_url_mismatch(state=_state, database_url=database_url)
        return _state.checkpointer

    async with _state_lock:
        if _state is not None:
            _raise_if_database_url_mismatch(state=_state, database_url=database_url)
            return _state.checkpointer
        _state = await _initialize_state(database_url=database_url)
        return _state.checkpointer


async def close_langgraph_postgres_checkpointer() -> None:
    global _state

    async with _state_lock:
        if _state is None:
            return
        await _state.context_manager.__aexit__(None, None, None)
        _state = None


async def _initialize_state(*, database_url: str) -> _CheckpointerState:
    postgres_url = _as_langgraph_postgres_url(database_url)
    context_manager = AsyncPostgresSaver.from_conn_string(postgres_url)
    checkpointer = await context_manager.__aenter__()
    try:
        # setup() is idempotent; this creates checkpoint tables on first boot.
        await checkpointer.setup()
    except Exception:
        await context_manager.__aexit__(None, None, None)
        raise

    return _CheckpointerState(
        context_manager=context_manager,
        checkpointer=checkpointer,
        database_url=database_url,
    )


def _raise_if_database_url_mismatch(*, state: _CheckpointerState, database_url: str) -> None:
    if state.database_url != database_url:
        msg = 'LangGraph checkpointer already initialized with a different database URL'
        raise RuntimeError(msg)


def _as_langgraph_postgres_url(database_url: str) -> str:
    if database_url.startswith('postgresql+psycopg://'):
        return database_url.replace('postgresql+psycopg://', 'postgresql://', 1)
    if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
        return database_url

    msg = 'LangGraph Postgres checkpointer requires a PostgreSQL database URL'
    raise ValueError(msg)
