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
    tracker_detail: str = ""       # e.g. "Claude - Writing code…" or "app.js · yoyo-dev"
    tracker_title: str = ""        # raw window title


class YoYoAgent:
    def __init__(self):
        self.state = AgentState()
        self._task: DevTask | None = None
        self._task_start: float = 0.0
        self._task_end: float = 0.0
        # Broadcast callback (set when run_loop starts)
        self._broadcast: Callable | None = None

    # ── Tracker integration ────────────────────────────────────
    def set_tracker_state(self, state: str, detail: str, window_title: str = "") -> bool:
        """
        Called by the /api/tracker endpoint.
        Returns True if anything changed (so the caller can broadcast).
        """
        changed = (
            self.state.tracker_state != state
            or self.state.tracker_detail != detail
        )
        self.state.tracker_state = state
        self.state.tracker_detail = detail
        self.state.tracker_title  = window_title
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
            "tracker_title":       s.tracker_title,
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
        """
        s = self.state
        detail = s.tracker_detail or s.tracker_title[:60]

        if s.tracker_state == "AI_WEB":
            tl = (s.tracker_title or s.tracker_detail or "").lower()
            if "antigravity" in tl:
                emoji = "🪐"
                name  = f"Antigravity: {detail}" if detail else "Antigravity IDE is working…"
            elif "claude" in tl:
                emoji = "🤖"
                name  = f"Claude: {detail}" if detail else "Claude is thinking…"
            elif "chatgpt" in tl:
                emoji = "💬"
                name  = f"ChatGPT: {detail}" if detail else "ChatGPT is responding…"
            elif "gemini" in tl:
                emoji = "✨"
                name  = f"Gemini: {detail}" if detail else "Gemini is working…"
            else:
                emoji = "🌐"
                name  = f"AI: {detail}" if detail else "AI Web — working…"
            return emoji, name, detail

        if s.tracker_state == "IDE":
            emoji = "💻"
            name  = f"Coding: {detail}" if detail else "Coding in IDE…"
            return emoji, name, detail

        return "⏸", "Idle", ""

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

                    # Stay in this mode, updating every 3 s, until tracker changes
                    elapsed = 0.0
                    while self.state.tracker_state in ("AI_WEB", "IDE"):
                        await asyncio.sleep(3)
                        elapsed += 3.0

                        # Re-read in case window title / detail changed
                        emoji, name, detail = self._real_task_info()
                        self.state.current_task = name
                        self.state.current_task_emoji = emoji
                        # Gentle pulsing progress bar (never reaches 100 while active)
                        self.state.progress = min(0.05 + (elapsed % 60) / 65, 0.95)

                        await broadcast({"type": "agent_state", **self.get_state()})

                    # Tracker went IDLE → mark done
                    self.state.status = AgentStatus.DONE
                    self.state.progress = 1.0
                    self.state.tasks_completed += 1
                    self.state.task_history.append({
                        "task":     name,
                        "emoji":    emoji,
                        "pts":      0,
                        "time":     int(time.time()),
                        "duration": round(elapsed, 1),
                        "real":     True,
                    })
                    await broadcast({"type": "agent_state", **self.get_state()})
                    await asyncio.sleep(2)

                    # Back to IDLE
                    self.state.status = AgentStatus.IDLE
                    self.state.current_task = ""
                    self.state.current_task_emoji = ""
                    self.state.progress = 0.0
                    await broadcast({"type": "agent_state", **self.get_state()})

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

