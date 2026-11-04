"""YoYoAgent aggregate root.

All business rules live here: what a task is, when it expires, how points are
earned, how fast tricks may be performed. The aggregate never talks to the
network, the clock or the RNG directly — time and randomness are passed in.
"""

import random
from dataclasses import dataclass, field

from .errors import NoActiveTask, TrickOnCooldown
from .events import (
    AgentStateChanged,
    DomainEvent,
    NotificationRaised,
    TaskProgressed,
    TrackerChanged,
    TrickPerformed,
)
from .value_objects import (
    AgentStatus,
    BonusPoints,
    NotificationLevel,
    Progress,
    TaskLabel,
    TaskSource,
    TrackerState,
    Trick,
)

TRICK_COOLDOWN_SECONDS = 0.5
HISTORY_LIMIT = 50
CHUNK_MIN_SECONDS = 15.0
CHUNK_MAX_SECONDS = 35.0
MIN_REWARDED_CHUNK_SECONDS = 3.0
DONE_DISPLAY_SECONDS = 2.0


@dataclass
class TrackerSnapshot:
    state: TrackerState = TrackerState.IDLE
    detail: str = ""
    emoji: str = ""
    window_title: str = ""
    process: str = ""


@dataclass
class YoYoAgent:
    started_at: float
    status: AgentStatus = AgentStatus.IDLE
    task: TaskLabel | None = None
    progress: Progress = field(default_factory=Progress)
    source: TaskSource | None = None
    tasks_completed: int = 0
    total_bonus_pts: int = 0
    score: int = 0
    tricks_done: int = 0
    history: list[dict] = field(default_factory=list)
    tracker: TrackerSnapshot = field(default_factory=TrackerSnapshot)

    # bookkeeping for time-based rules
    _last_external_at: float = 0.0
    _lease: float | None = None  # per-task override of the staleness TTL
    _last_trick_at: float = -1e9
    _chunk_started_at: float | None = None
    _chunk_duration: float = 0.0
    _done_at: float = 0.0
    _resume_at: float = 0.0
    _events: list[DomainEvent] = field(default_factory=list, repr=False)

    # ── events ─────────────────────────────────────────────────
    def _raise(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events

    # ── tasks pushed by an external AI agent ───────────────────
    def start_task(self, label: TaskLabel, now: float, lease: float | None = None) -> None:
        self.status = AgentStatus.WORKING
        self.task = label
        self.progress = Progress(0.0)
        self.source = TaskSource.EXTERNAL
        self._last_external_at = now
        self._lease = lease
        self._chunk_started_at = None
        self._raise(AgentStateChanged())

    def update_task(self, label: TaskLabel | None, progress: Progress | None, now: float,
                    lease: float | None = None) -> None:
        """Report a step. Implicitly starts a task if none is running."""
        if self.status != AgentStatus.WORKING or self.source != TaskSource.EXTERNAL:
            self.start_task(label or self.task or TaskLabel("Working…"), now, lease)
        if label is not None:
            self.task = label
        if progress is not None:
            self.progress = progress
        self._last_external_at = now
        if lease is not None:
            self._lease = lease
        self._raise(AgentStateChanged())
        self._raise(TaskProgressed())

    def complete_task(self, now: float) -> None:
        if self.status != AgentStatus.WORKING:
            raise NoActiveTask("There is no task in progress to complete")
        self.status = AgentStatus.DONE
        self.progress = Progress(1.0)
        self.tasks_completed += 1
        self._done_at = now
        self._chunk_started_at = None
        self._raise(AgentStateChanged())

    def is_external_task_stale(self, now: float, ttl: float) -> bool:
        return (
            self.status == AgentStatus.WORKING
            and self.source == TaskSource.EXTERNAL
            and now - self._last_external_at > (self._lease or ttl)
        )

    def has_live_external_task(self, now: float, ttl: float) -> bool:
        return (
            self.status == AgentStatus.WORKING
            and self.source == TaskSource.EXTERNAL
            and not self.is_external_task_stale(now, ttl)
        )

    # ── rewards ────────────────────────────────────────────────
    def perform_trick(self, trick: Trick, now: float) -> None:
        if now - self._last_trick_at < TRICK_COOLDOWN_SECONDS:
            raise TrickOnCooldown("The yo-yo is still recovering from the last trick")
        self._last_trick_at = now
        self.score += trick.points
        self.tricks_done += 1
        self._raise(TrickPerformed(trick_id=trick.trick_id, points=trick.points))

    def notify(self, title: str, message: str, bonus: BonusPoints,
               level: NotificationLevel, duration: int = 0) -> None:
        self.total_bonus_pts += bonus.value
        self._raise(NotificationRaised(
            title=title, message=message, bonus_pts=bonus.value,
            level=level.value, duration=duration,
        ))

    # ── what the human is doing ────────────────────────────────
    def change_tracker(self, snapshot: TrackerSnapshot) -> bool:
        changed = (
            self.tracker.state != snapshot.state or self.tracker.detail != snapshot.detail
        )
        self.tracker = snapshot
        self._raise(TrackerChanged(
            state=snapshot.state.value, detail=snapshot.detail, emoji=snapshot.emoji,
            window_title=snapshot.window_title, process=snapshot.process,
        ))
        return changed

    @property
    def player_present(self) -> bool:
        return self.tracker.state == TrackerState.PLAYING

    # ── lifecycle ──────────────────────────────────────────────
    def reset(self) -> None:
        self._go_idle()
        self._raise(AgentStateChanged())

    def _go_idle(self) -> None:
        self.status = AgentStatus.IDLE
        self.task = None
        self.progress = Progress(0.0)
        self.source = None
        self._lease = None
        self._chunk_started_at = None

    # ── periodic state machine ─────────────────────────────────
    def tick(self, now: float, rng: random.Random, external_ttl: float) -> None:
        """Advance time-based behaviour; called every couple of seconds.

        * A live external task (Claude pushing real steps) always wins.
        * A stale external task (Claude went silent) is dropped.
        * Otherwise, while the human is in an AI/IDE window, work is shown in
          "chunks" that end with a reward notification.
        """
        if self.is_external_task_stale(now, external_ttl):
            self._go_idle()
            self._raise(AgentStateChanged())
            return
        if self.has_live_external_task(now, external_ttl):
            return

        # keep DONE visible for a moment, then fall back to IDLE
        if self.status == AgentStatus.DONE and now - self._done_at >= DONE_DISPLAY_SECONDS:
            self._go_idle()
            self._raise(AgentStateChanged())

        if self.tracker.state.is_working_context:
            self._tick_tracked_work(now, rng)
        elif self._chunk_started_at is not None:
            self._finish_chunk(now, rng)
        elif self.status == AgentStatus.WORKING:
            self._go_idle()
            self._raise(AgentStateChanged())

    def _tick_tracked_work(self, now: float, rng: random.Random) -> None:
        if self._chunk_started_at is None:
            if now < self._resume_at:
                return
            self.status = AgentStatus.WORKING
            self.source = TaskSource.TRACKER
            self._chunk_started_at = now
            self._chunk_duration = rng.uniform(CHUNK_MIN_SECONDS, CHUNK_MAX_SECONDS)
            self.progress = Progress(0.0)

        self.task = self._tracked_label()
        elapsed = now - self._chunk_started_at
        if elapsed >= self._chunk_duration:
            self._finish_chunk(now, rng)
            return
        self.progress = Progress.clamp(elapsed / self._chunk_duration)
        self._raise(AgentStateChanged())

    def _tracked_label(self) -> TaskLabel:
        t = self.tracker
        name = t.detail or t.window_title[:60] or (
            "Coding in IDE…" if t.state == TrackerState.IDE else "AI is working…"
        )
        emoji = t.emoji or ("💻" if t.state == TrackerState.IDE else "🌐")
        return TaskLabel(name, emoji)

    def _finish_chunk(self, now: float, rng: random.Random) -> None:
        started = self._chunk_started_at if self._chunk_started_at is not None else now
        elapsed = now - started
        self._chunk_started_at = None
        label = self.task or self._tracked_label()
        if elapsed < MIN_REWARDED_CHUNK_SECONDS:
            self._go_idle()
            self._raise(AgentStateChanged())
            return

        bonus = int(elapsed * 5) + rng.randint(20, 80)
        self.status = AgentStatus.DONE
        self.progress = Progress(1.0)
        self.tasks_completed += 1
        self.total_bonus_pts += bonus
        self._done_at = now
        self._resume_at = now + rng.uniform(4, 7)
        self.history.append({
            "task": label.name, "emoji": label.emoji, "pts": bonus,
            "time": int(now), "duration": round(elapsed, 1), "real": True,
        })
        del self.history[:-HISTORY_LIMIT]
        self._raise(AgentStateChanged())
        self._raise(NotificationRaised(
            title=f"{label.emoji} Task Complete",
            message=rng.choice([
                f"Awesome progress on {label.name[:15]}...",
                "Code is flowing nicely! 💻",
                "One step closer to release! 🚀",
                "AI and Human in perfect harmony 🤖🤝",
                "Another chunk of work completed! ✅",
            ]),
            bonus_pts=bonus, level=NotificationLevel.SUCCESS.value,
            duration=int(round(elapsed)),
        ))
