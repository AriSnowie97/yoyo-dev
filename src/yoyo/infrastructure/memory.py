"""In-memory adapters for the repository and Unit of Work ports.

The store hands out *copies* of the aggregate and the lock is held for the
whole transaction, so a failed or abandoned transaction leaves no trace and
concurrent transactions are serialized (the same guarantees a real database
gives, which makes swapping this adapter for SQLite/Postgres a local change).
"""

import asyncio
import copy

from ..application.ports import UnitOfWork
from ..domain.agent import YoYoAgent
from ..domain.repositories import AgentRepository


class InMemoryAgentStore:
    def __init__(self, initial: YoYoAgent) -> None:
        self.agent = initial
        self.lock = asyncio.Lock()


class InMemoryAgentRepository(AgentRepository):
    def __init__(self, store: InMemoryAgentStore) -> None:
        self._store = store
        self.pending: YoYoAgent | None = None

    async def get(self) -> YoYoAgent:
        return copy.deepcopy(self._store.agent)

    async def save(self, agent: YoYoAgent) -> None:
        self.pending = agent


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self, store: InMemoryAgentStore) -> None:
        self._store = store
        self._repo = InMemoryAgentRepository(store)
        self.agents = self._repo
        self.events = []

    async def __aenter__(self) -> "InMemoryUnitOfWork":
        await self._store.lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await self.rollback()
        finally:
            self._store.lock.release()

    async def commit(self) -> None:
        pending = self._repo.pending
        if pending is not None:
            self.events = pending.pull_events()
            self._store.agent = pending
            self._repo.pending = None

    async def rollback(self) -> None:
        self._repo.pending = None
