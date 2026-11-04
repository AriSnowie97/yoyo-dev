"""Read models. Domain objects never leave the application layer."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentStateDTO:
    status: str
    current_task: str
    current_task_emoji: str
    progress: float
    task_source: str
    tasks_completed: int
    total_bonus_pts: int
    score: int
    tricks_done: int
    uptime: int
    task_history: list[dict] = field(default_factory=list)
    tracker_state: str = "IDLE"
    tracker_detail: str = ""
    tracker_emoji: str = ""
    tracker_title: str = ""
    tracker_process: str = ""
    player_present: bool = False


@dataclass(frozen=True)
class StatsDTO:
    score: int
    tricks_done: int
    tasks_completed: int
    total_bonus_pts: int
    uptime_seconds: int


@dataclass(frozen=True)
class TrickResultDTO:
    trick: str
    points: int
    score: int
