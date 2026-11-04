"""Application services: orchestrate use cases, hold no business rules.

* ``GameCommandService`` — write side. Every method is one Unit of Work:
  load aggregate -> call domain behaviour -> commit -> publish events.
* ``GameQueryService`` — read side, backed by a TTL cache that is invalidated
  by domain events.
"""

import random
from typing import Callable, TypeVar

from ..domain.agent import TrackerSnapshot, YoYoAgent
from ..domain.errors import InvalidValue
from ..domain.value_objects import (
    BonusPoints,
    NotificationLevel,
    Progress,
    TaskLabel,
    TrackerState,
    Trick,
)
from . import mappers
from .cache import TTLCache
from .commands import PerformTrick, RaiseNotification, ReportTracker, StartTask, UpdateTask
from .dto import AgentStateDTO, StatsDTO, TrickResultDTO
from .ports import Clock, EventBus, UnitOfWorkFactory

T = TypeVar("T")


class GameCommandService:
    def __init__(self, uow_factory: UnitOfWorkFactory, bus: EventBus, clock: Clock,
                 rng: random.Random, external_task_ttl: float) -> None:
        self._uow_factory = uow_factory
        self._bus = bus
        self._clock = clock
        self._rng = rng
        self._external_task_ttl = external_task_ttl

    async def _transaction(self, action: Callable[[YoYoAgent], T]) -> T:
        async with self._uow_factory() as uow:
            agent = await uow.agents.get()
            result = action(agent)
            await uow.agents.save(agent)
            await uow.commit()
            events = uow.events
        # published only after a successful commit
        await self._bus.publish_all(events)
        return result

    async def start_task(self, cmd: StartTask) -> None:
        label = TaskLabel(cmd.name, cmd.emoji)
        await self._transaction(lambda agent: agent.start_task(label, self._clock.now()))

    async def update_task(self, cmd: UpdateTask) -> None:
        def action(agent: YoYoAgent) -> None:
            label = None
            if cmd.name is not None or cmd.emoji is not None:
                current = agent.task
                label = TaskLabel(
                    cmd.name if cmd.name is not None else (current.name if current else "Working…"),
                    cmd.emoji or (current.emoji if current else "⚙️"),
                )
            progress = Progress(cmd.progress) if cmd.progress is not None else None
            agent.update_task(label, progress, self._clock.now())

        await self._transaction(action)

    async def complete_task(self) -> None:
        await self._transaction(lambda agent: agent.complete_task(self._clock.now()))

    async def reset(self) -> None:
        await self._transaction(lambda agent: agent.reset())

    async def perform_trick(self, cmd: PerformTrick) -> TrickResultDTO:
        trick = Trick.by_title(cmd.trick_name)

        def action(agent: YoYoAgent) -> TrickResultDTO:
            agent.perform_trick(trick, self._clock.now())
            return TrickResultDTO(trick=trick.title, points=trick.points, score=agent.score)

        return await self._transaction(action)

    async def notify(self, cmd: RaiseNotification) -> None:
        bonus = BonusPoints(cmd.bonus_pts)
        try:
            level = NotificationLevel(cmd.level)
        except ValueError:
            raise InvalidValue(f"Unknown notification level: {cmd.level!r}") from None
        await self._transaction(
            lambda agent: agent.notify(cmd.title, cmd.message, bonus, level)
        )

    async def report_tracker(self, cmd: ReportTracker) -> bool:
        try:
            state = TrackerState(cmd.state)
        except ValueError:
            raise InvalidValue(f"Unknown tracker state: {cmd.state!r}") from None
        snapshot = TrackerSnapshot(state, cmd.detail, cmd.emoji, cmd.window_title, cmd.process)
        return await self._transaction(lambda agent: agent.change_tracker(snapshot))

    async def tick(self) -> None:
        await self._transaction(
            lambda agent: agent.tick(self._clock.now(), self._rng, self._external_task_ttl)
        )


class GameQueryService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, cache_ttl: float) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._state_cache: TTLCache[AgentStateDTO] = TTLCache(clock, cache_ttl)
        self._stats_cache: TTLCache[StatsDTO] = TTLCache(clock, cache_ttl)

    async def get_state(self) -> AgentStateDTO:
        async def load() -> AgentStateDTO:
            async with self._uow_factory() as uow:
                return mappers.agent_to_state_dto(await uow.agents.get(), self._clock.now())

        return await self._state_cache.get_or_load("state", load)

    async def get_stats(self) -> StatsDTO:
        async def load() -> StatsDTO:
            async with self._uow_factory() as uow:
                return mappers.agent_to_stats_dto(await uow.agents.get(), self._clock.now())

        return await self._stats_cache.get_or_load("stats", load)

    def invalidate(self) -> None:
        self._state_cache.invalidate_all()
        self._stats_cache.invalidate_all()
