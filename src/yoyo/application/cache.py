"""Tiny TTL cache for the read side.

Entries expire after ``ttl`` seconds *and* are dropped explicitly whenever a
domain event says the underlying state changed (see ``invalidate_all``).
"""

from typing import Awaitable, Callable, Generic, TypeVar

from .ports import Clock

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, clock: Clock, ttl: float) -> None:
        self._clock = clock
        self._ttl = ttl
        self._items: dict[str, tuple[float, T]] = {}
        self.hits = 0
        self.misses = 0

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[T]]) -> T:
        now = self._clock.now()
        entry = self._items.get(key)
        if entry is not None and now - entry[0] < self._ttl:
            self.hits += 1
            return entry[1]
        self.misses += 1
        value = await loader()
        self._items[key] = (self._clock.now(), value)
        return value

    def invalidate_all(self) -> None:
        self._items.clear()
