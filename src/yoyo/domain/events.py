"""Domain events — facts that already happened inside the aggregate."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainEvent:
    """Marker base class; subscribers register for concrete subclasses."""


@dataclass(frozen=True)
class AgentStateChanged(DomainEvent):
    """Anything visible in the HUD changed (status, task, progress, tracker)."""


@dataclass(frozen=True)
class TaskProgressed(DomainEvent):
    """An explicit step update was pushed (adds a line to the HUD log)."""


@dataclass(frozen=True)
class TrickPerformed(DomainEvent):
    trick_id: str
    points: int


@dataclass(frozen=True)
class NotificationRaised(DomainEvent):
    title: str
    message: str
    bonus_pts: int
    level: str
    duration: int = 0


@dataclass(frozen=True)
class TrackerChanged(DomainEvent):
    state: str
    detail: str
    emoji: str
    window_title: str
    process: str
