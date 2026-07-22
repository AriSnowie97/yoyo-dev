"""
YoYo Agent v2 🤖 — Background agent that simulates dev tasks
and broadcasts notifications to the player when done.

When the AI-tracker reports that Claude / an IDE is active,
the agent surfaces REAL activity instead of simulated tasks.
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class AgentStatus(str, Enum):
    IDLE    = "IDLE"
    WORKING = "WORKING"
    DONE    = "DONE"


# ── Simulated dev tasks (used when tracker says IDLE) ──────────
@dataclass
class DevTask:
    name: str
    emoji: str
    duration_min: float   # seconds
    duration_max: float
    bonus_pts: int
    done_message: str


TASKS: list[DevTask] = [
    DevTask("Deploying to Railway",    "🚂", 15, 30, 500, "Railway deploy complete! Your app is live 🎉"),
    DevTask("Running ML training",     "🧠", 20, 40, 400, "Model training done! Accuracy: 94.7%"),
    DevTask("Code review",             "🔍", 10, 25, 200, "Code reviewed — 3 issues fixed, LGTM 👍"),
    DevTask("Running unit tests",      "🧪",  8, 18, 150, "All 247 tests passed ✅"),
    DevTask("Building Docker image",   "🐳", 12, 22, 250, "Docker image built and pushed!"),
    DevTask("Fetching API data",       "🌐",  5, 12, 100, "Data fetched — 1,337 records processed"),
    DevTask("Database migration",      "🗄️", 10, 20, 300, "Migration complete — no data lost!"),
    DevTask("Generating embeddings",   "🔮", 15, 25, 350, "Embeddings ready — 50k vectors indexed"),
    DevTask("Security scan",           "🔒",  8, 16, 200, "Scan complete — no vulnerabilities found 🛡"),
    DevTask("Optimizing queries",      "⚡",  6, 14, 175, "Queries optimized — 3x faster now!"),
    DevTask("Sending email reports",   "📧",  4,  8,  80, "Reports sent to 42 recipients"),
    DevTask("Backing up data",         "💾", 10, 20, 220, "Backup done — 2.3 GB saved safely"),
    DevTask("Scraping web data",       "🕷️",  8, 18, 130, "Scraped 890 pages, dataset ready"),
    DevTask("Analyzing logs",          "📊",  6, 12, 160, "Log analysis done — 5 anomalies detected"),
    DevTask("Updating dependencies",   "📦",  5, 10, 120, "All packages updated to latest versions!"),
]


@dataclass
class AgentState:
    status: AgentStatus = AgentStatus.IDLE
    current_task: str = ""
    current_task_emoji: str = ""
    progress: float = 0.0          # 0.0 – 1.0
    tasks_completed: int = 0
    total_bonus_pts: int = 0
    score: int = 0
    tricks_done: int = 0
    task_history: list = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    # Real-time tracker fields
    tracker_state: str = "IDLE"    # "IDLE" | "AI_WEB" | "IDE"
    tracker_detail: str = ""       # e.g. "Claude Desktop: Writing code"
    tracker_emoji: str = ""        # emoji from ai_tracker
    tracker_title: str = ""        # raw window title
    tracker_process: str = ""      # exe name e.g. "claude.exe"


class YoYoAgent:
    def __init__(self):
        self.state = AgentState()
        self._task: DevTask | None = None
        self._task_start: float = 0.0
        self._task_end: float = 0.0
        # Broadcast callback (set when run_loop starts)
        self._broadcast: Callable | None = None

    # ── Tracker integration ────────────────────────────────────
    def set_tracker_state(self, state: str, detail: str, window_title: str = "",
                          emoji: str = "", process: str = "") -> bool:
        """
        Called by the /api/tracker endpoint.
        Returns True if anything changed (so the caller can broadcast).
        """
        changed = (
            self.state.tracker_state != state
            or self.state.tracker_detail != detail
        )
        self.state.tracker_state   = state
        self.state.tracker_detail  = detail
        self.state.tracker_emoji   = emoji
        self.state.tracker_title   = window_title
        self.state.tracker_process = process
        return changed

    def get_state(self) -> dict:
        s = self.state
        return {
            "status":              s.status.value,
            "current_task":        s.current_task,
            "current_task_emoji":  s.current_task_emoji,
            "progress":            round(s.progress, 2),
            "tasks_completed":     s.tasks_completed,
            "total_bonus_pts":     s.total_bonus_pts,
            "task_history":        s.task_history[-8:],
            "uptime":              int(time.time() - s.started_at),
            # Real tracker data
            "tracker_state":       s.tracker_state,
            "tracker_detail":      s.tracker_detail,
            "tracker_emoji":       s.tracker_emoji,
            "tracker_title":       s.tracker_title,
            "tracker_process":     s.tracker_process,
        }

    def get_stats(self) -> dict:
        s = self.state
        return {
            "score":           s.score,
            "tricks_done":     s.tricks_done,
            "tasks_completed": s.tasks_completed,
            "uptime_seconds":  int(time.time() - s.started_at),
        }

    def reset(self):
        self.state.status = AgentStatus.IDLE
        self.state.current_task = ""
        self.state.current_task_emoji = ""
        self.state.progress = 0.0

    # ── Real-activity task builder ─────────────────────────────
    def _real_task_info(self) -> tuple[str, str, str]:
        """
        Returns (emoji, task_name, sub_detail) based on current tracker state.
        emoji comes directly from ai_tracker — no need to guess by title.
        """
        s = self.state
        detail = s.tracker_detail or s.tracker_title[:60]
        emoji  = s.tracker_emoji or ("💻" if s.tracker_state == "IDE" else "🌐")
        name   = detail if detail else (
            "Coding in IDE…" if s.tracker_state == "IDE" else "AI is working…"
        )
        return emoji, name, detail

    # ── Main agent loop ────────────────────────────────────────
    async def run_loop(self, broadcast: Callable):
        self._broadcast = broadcast
        await asyncio.sleep(3)  # warm-up

        while True:
            try:
                tracker = self.state.tracker_state

                # ── If AI or IDE is active — show real status ──
                if tracker in ("AI_WEB", "IDE"):
                    emoji, name, detail = self._real_task_info()

                    self.state.status = AgentStatus.WORKING
                    self.state.current_task = name
                    self.state.current_task_emoji = emoji
                    self.state.progress = 0.0

                    await broadcast({"type": "agent_state", **self.get_state()})

                    duration = random.uniform(15, 35)
                    task_start = time.time()
                    task_end = task_start + duration

                    # Loop until duration is reached OR tracker goes IDLE
                    while self.state.tracker_state in ("AI_WEB", "IDE") and time.time() < task_end:
                        await asyncio.sleep(2)

                        # Re-read in case window title / detail changed
                        new_emoji, new_name, _ = self._real_task_info()
                        self.state.current_task = new_name
                        self.state.current_task_emoji = new_emoji
                        
                        elapsed = time.time() - task_start
                        self.state.progress = min(elapsed / duration, 1.0)

                        await broadcast({"type": "agent_state", **self.get_state()})

                    elapsed = time.time() - task_start
                    if elapsed >= 3.0:
                        # Chunk completed (or interrupted after some work)
                        self.state.status = AgentStatus.DONE
                        self.state.progress = 1.0
                        self.state.tasks_completed += 1
                        
                        bonus = int(elapsed * 5) + random.randint(20, 80)
                        self.state.total_bonus_pts += bonus
                        
                        self.state.task_history.append({
                            "task":     self.state.current_task,
                            "emoji":    self.state.current_task_emoji,
                            "pts":      bonus,
                            "time":     int(time.time()),
                            "duration": round(elapsed, 1),
                            "real":     True,
                        })
                        await broadcast({"type": "agent_state", **self.get_state()})
                        
                        done_msgs = [
                            f"Awesome progress on {self.state.current_task[:15]}...",
                            "Code is flowing nicely! 💻",
                            "One step closer to release! 🚀",
                            "AI and Human in perfect harmony 🤖🤝",
                            "Another chunk of work completed! ✅"
                        ]
                        
                        await asyncio.sleep(0.2)
                        await broadcast({
                            "type": "notification",
                            "title": f"{self.state.current_task_emoji} Task Complete",
                            "message": random.choice(done_msgs),
                            "bonus_pts": bonus,
                            "level": "success",
                            "duration": round(elapsed, 0),
                        })
                        await asyncio.sleep(2)

                    # Back to IDLE before the next loop iteration evaluates
                    self.state.status = AgentStatus.IDLE
                    self.state.current_task = ""
                    self.state.current_task_emoji = ""
                    self.state.progress = 0.0
                    await broadcast({"type": "agent_state", **self.get_state()})
                    
                    if self.state.tracker_state in ("AI_WEB", "IDE"):
                        # Short rest before picking up the next chunk of the real task
                        await asyncio.sleep(random.uniform(2, 5))

                else:
                    # ── IDLE: just wait, no fake tasks ──
                    self.state.status = AgentStatus.IDLE
                    self.state.current_task = ""
                    self.state.current_task_emoji = ""
                    self.state.progress = 0.0
                    # Broadcast only if something changed
                    await broadcast({"type": "agent_state", **self.get_state()})
                    await asyncio.sleep(3)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Agent loop error: {e}")
                await asyncio.sleep(5)

