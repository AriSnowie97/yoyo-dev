"""Runtime configuration, read once from the environment."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # An AI agent that stops reporting for this long is considered gone.
    external_task_ttl: float = 90.0
    # Read-side cache lifetime (also invalidated by every domain event).
    cache_ttl: float = 1.0
    tick_interval: float = 2.0
    warmup_delay: float = 3.0

    @classmethod
    def from_env(cls) -> "Settings":
        def number(name: str, default: float) -> float:
            try:
                return float(os.environ.get(name, default))
            except ValueError:
                return default

        return cls(
            external_task_ttl=number("YOYO_TASK_TTL", cls.external_task_ttl),
            cache_ttl=number("YOYO_CACHE_TTL", cls.cache_ttl),
        )
