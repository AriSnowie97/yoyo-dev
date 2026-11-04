"""Ports the application layer depends on (Dependency Inversion).

Concrete adapters live in ``yoyo.infrastructure``; they are wired together in
``yoyo.container``.
"""

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from ..domain.events import DomainEvent
from ..domain.repositories import AgentRepository

EventHandler = Callable[[DomainEvent], Awaitable[None]]


class Clock(ABC):
    @abstractmethod
    def now(self) -> float: ...


class EventBus(ABC):
    @abstractmethod
    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None: ...

    @abstractmethod
    async def publish_all(self, events: list[DomainEvent]) -> None: ...


class UnitOfWork(ABC):
    """One atomic business transaction.

    Changes become visible only on ``commit()``; leaving the block without
    committing (or with an exception) discards them. Domain events raised by
    the aggregates are exposed in ``events`` after a successful commit, so they
    can be published only for changes that were really persisted.
    """

    agents: AgentRepository
    events: list[DomainEvent]

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.rollback()

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]
