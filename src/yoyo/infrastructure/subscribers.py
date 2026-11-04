"""Event handlers: the reactions to domain events.

Adding a reaction means adding a handler and one ``subscribe`` line in the
container — no existing code changes (Open/Closed).
"""

from ..application import mappers
from ..application.services import GameQueryService
from ..domain.events import (
    AgentStateChanged,
    DomainEvent,
    NotificationRaised,
    TaskProgressed,
    TrackerChanged,
    TrickPerformed,
)
from .ws_hub import WebSocketHub


class CacheInvalidator:
    """Must be subscribed *before* the broadcaster so it reads fresh state."""

    def __init__(self, queries: GameQueryService) -> None:
        self._queries = queries

    async def __call__(self, event: DomainEvent) -> None:
        self._queries.invalidate()


class WebSocketBroadcaster:
    def __init__(self, hub: WebSocketHub, queries: GameQueryService) -> None:
        self._hub = hub
        self._queries = queries

    async def on_state_changed(self, event: AgentStateChanged) -> None:
        await self._hub.broadcast(mappers.state_to_wire(await self._queries.get_state()))

    async def on_task_progressed(self, event: TaskProgressed) -> None:
        await self._hub.broadcast(mappers.task_log_to_wire(await self._queries.get_state()))

    async def on_trick(self, event: TrickPerformed) -> None:
        await self._hub.broadcast(mappers.trick_to_wire(event))

    async def on_notification(self, event: NotificationRaised) -> None:
        await self._hub.broadcast(mappers.notification_to_wire(event))

    async def on_tracker(self, event: TrackerChanged) -> None:
        await self._hub.broadcast(mappers.tracker_to_wire(event))
