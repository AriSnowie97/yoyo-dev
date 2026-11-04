"""In-process event bus.

Handlers run in registration order. A failing handler is logged and never
breaks the business operation that raised the event (events are notifications,
not part of the transaction).
"""

import logging

from ..domain.events import DomainEvent
from .ports import EventBus, EventHandler

logger = logging.getLogger(__name__)


class InProcessEventBus(EventBus):
    def __init__(self) -> None:
        self._handlers: list[tuple[type[DomainEvent], EventHandler]] = []

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers.append((event_type, handler))

    async def publish_all(self, events: list[DomainEvent]) -> None:
        for event in events:
            for event_type, handler in self._handlers:
                if not isinstance(event, event_type):
                    continue
                try:
                    await handler(event)
                except Exception:
                    logger.exception("Handler %s failed for %s", handler, type(event).__name__)
