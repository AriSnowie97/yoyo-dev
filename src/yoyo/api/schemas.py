"""Request schemas — shape validation at the system boundary.

These guard types, lengths and ranges. Rules about *meaning* (cooldowns,
"no task to complete", ...) are enforced by the domain.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..application.commands import (
    PerformTrick,
    RaiseNotification,
    ReportTracker,
    StartTask,
    UpdateTask,
)


class _Request(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class StartTaskRequest(_Request):
    task_name: str = Field("External Task", min_length=1, max_length=120)
    emoji: str = Field("🤖", max_length=16)

    def to_command(self) -> StartTask:
        return StartTask(self.task_name, self.emoji)


class UpdateTaskRequest(_Request):
    task_name: str | None = Field(None, min_length=1, max_length=120)
    emoji: str | None = Field(None, max_length=16)
    progress: float | None = Field(None, ge=0.0, le=1.0)

    def to_command(self) -> UpdateTask:
        return UpdateTask(self.task_name, self.emoji, self.progress)


class TrickRequest(_Request):
    trick_name: str = Field(..., min_length=1, max_length=40)

    def to_command(self) -> PerformTrick:
        return PerformTrick(self.trick_name)


class NotifyRequest(_Request):
    title: str = Field("✅ Done", min_length=1, max_length=120)
    message: str = Field("", max_length=500)
    bonus_pts: int = Field(0, ge=0, le=500)
    level: Literal["success", "info", "warning", "error"] = "success"

    def to_command(self) -> RaiseNotification:
        return RaiseNotification(self.title, self.message, self.bonus_pts, self.level)


class TrackerRequest(_Request):
    state: Literal["IDLE", "AI_WEB", "IDE", "PLAYING"] = "IDLE"
    detail: str = Field("", max_length=200)
    emoji: str = Field("", max_length=16)
    window_title: str = Field("", max_length=300)
    process: str = Field("", max_length=100)

    def to_command(self) -> ReportTracker:
        return ReportTracker(self.state, self.detail, self.emoji, self.window_title, self.process)
