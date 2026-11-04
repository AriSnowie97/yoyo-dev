"""Immutable, self-validating value objects and enums of the YoYo domain."""

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidValue, UnknownTrick

MAX_TASK_NAME = 120
MAX_BONUS_POINTS = 500


class AgentStatus(str, Enum):
    IDLE = "IDLE"
    WORKING = "WORKING"
    DONE = "DONE"


class TrackerState(str, Enum):
    """What the *human* is looking at right now (reported by ai_tracker)."""

    IDLE = "IDLE"
    AI_WEB = "AI_WEB"
    IDE = "IDE"
    PLAYING = "PLAYING"  # the human is in the YoYo window

    @property
    def is_working_context(self) -> bool:
        return self in (TrackerState.AI_WEB, TrackerState.IDE)


class TaskSource(str, Enum):
    EXTERNAL = "EXTERNAL"  # pushed by an AI agent through MCP / hooks
    TRACKER = "TRACKER"    # inferred from the active window


class NotificationLevel(str, Enum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Trick(Enum):
    SLEEPER = ("Sleeper", "sleeper", 5)
    WALK_THE_DOG = ("Walk the Dog", "walkdog", 10)
    ROCK_THE_BABY = ("Rock the Baby", "rockbaby", 15)
    AROUND_THE_WORLD = ("Around the World", "around", 25)
    LOOP_THE_LOOP = ("Loop the Loop", "loop", 30)
    EIFFEL_TOWER = ("Eiffel Tower", "eiffel", 35)
    ATOM_SMASHER = ("Atom Smasher", "atom", 45)
    STRING_BURN = ("String Burn", "string", 50)

    def __init__(self, title: str, trick_id: str, points: int):
        self.title = title
        self.trick_id = trick_id
        self.points = points

    @classmethod
    def by_title(cls, title: str) -> "Trick":
        for trick in cls:
            if trick.title == title:
                return trick
        raise UnknownTrick(f"Unknown trick: {title!r}")


@dataclass(frozen=True)
class Progress:
    value: float = 0.0

    def __post_init__(self):
        if not 0.0 <= self.value <= 1.0:
            raise InvalidValue(f"Progress must be within 0..1, got {self.value}")

    @classmethod
    def clamp(cls, value: float) -> "Progress":
        return cls(min(max(value, 0.0), 1.0))


@dataclass(frozen=True)
class TaskLabel:
    """Human readable task name + emoji, as shown in the HUD."""

    name: str
    emoji: str = "⚙️"

    def __post_init__(self):
        name = self.name.strip()
        if not name:
            raise InvalidValue("Task name must not be empty")
        if len(name) > MAX_TASK_NAME:
            raise InvalidValue(f"Task name is longer than {MAX_TASK_NAME} characters")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True)
class BonusPoints:
    value: int = 0

    def __post_init__(self):
        if not 0 <= self.value <= MAX_BONUS_POINTS:
            raise InvalidValue(f"Bonus points must be within 0..{MAX_BONUS_POINTS}")
