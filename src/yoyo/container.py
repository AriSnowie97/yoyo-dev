"""Composition root — the only place that knows concrete classes.

Everything else receives its dependencies through constructors (Dependency
Injection). Tests build the same container with a fake clock / seeded RNG.
"""

import random
from dataclasses import dataclass

from .application.claude_hooks import ClaudeActivityService
from .application.event_bus import InProcessEventBus
from .application.ports import Clock, EventBus
from .application.services import GameCommandService, GameQueryService
from .domain.agent import YoYoAgent
from .domain.events import (
    AgentStateChanged,
    DomainEvent,
    NotificationRaised,
    TaskProgressed,
    TrackerChanged,
    TrickPerformed,
)
from .infrastructure.clock import SystemClock
from .infrastructure.memory import InMemoryAgentStore, InMemoryUnitOfWork
from .infrastructure.subscribers import CacheInvalidator, WebSocketBroadcaster
from .infrastructure.worker import ActivityWorker
from .infrastructure.ws_hub import WebSocketHub
from .settings import Settings


@dataclass
class Container:
    settings: Settings
    clock: Clock
    bus: EventBus
    hub: WebSocketHub
    commands: GameCommandService
    queries: GameQueryService
    claude: ClaudeActivityService
    worker: ActivityWorker


def build_container(settings: Settings | None = None, clock: Clock | None = None,
                    rng: random.Random | None = None) -> Container:
    settings = settings or Settings.from_env()
    clock = clock or SystemClock()
    rng = rng or random.Random()

    store = InMemoryAgentStore(YoYoAgent(started_at=clock.now()))

    def uow_factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(store)

    bus = InProcessEventBus()
    hub = WebSocketHub()
    commands = GameCommandService(uow_factory, bus, clock, rng, settings.external_task_ttl)
    queries = GameQueryService(uow_factory, clock, settings.cache_ttl)

    # Order matters: invalidate the read cache first, then broadcast fresh data.
    bus.subscribe(DomainEvent, CacheInvalidator(queries))
    broadcaster = WebSocketBroadcaster(hub, queries)
    bus.subscribe(AgentStateChanged, broadcaster.on_state_changed)
    bus.subscribe(TaskProgressed, broadcaster.on_task_progressed)
    bus.subscribe(TrickPerformed, broadcaster.on_trick)
    bus.subscribe(NotificationRaised, broadcaster.on_notification)
    bus.subscribe(TrackerChanged, broadcaster.on_tracker)

    worker = ActivityWorker(commands, settings.tick_interval, settings.warmup_delay)
    claude = ClaudeActivityService(commands)
    return Container(settings, clock, bus, hub, commands, queries, claude, worker)
