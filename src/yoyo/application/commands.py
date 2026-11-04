"""Commands — the write-side input of the application layer.

Plain data, already validated by the API schemas; the *business* rules are
enforced by the domain.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StartTask:
    name: str
    emoji: str = "🤖"
    lease: float | None = None


@dataclass(frozen=True)
class UpdateTask:
    name: str | None = None
    emoji: str | None = None
    progress: float | None = None
    lease: float | None = None


@dataclass(frozen=True)
class PerformTrick:
    trick_name: str


@dataclass(frozen=True)
class RaiseNotification:
    title: str
    message: str
    bonus_pts: int = 0
    level: str = "success"


@dataclass(frozen=True)
class ReportTracker:
    state: str
    detail: str = ""
    emoji: str = ""
    window_title: str = ""
    process: str = ""
