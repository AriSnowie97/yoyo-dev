"""
YoYo Agent v2 🤖 — Background agent that simulates dev tasks
and broadcasts notifications to the player when done.
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


# ── Simulated dev tasks ───────────────────────────────────
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
    task_history: list = field(default_factory=list)
    started_at: float = field(default_factory=time.time)


class YoYoAgent:
    def __init__(self):
        self.state = AgentState()
        self._task: DevTask | None = None
        self._task_start: float = 0.0
        self._task_end: float = 0.0

    def get_state(self) -> dict:
        s = self.state
        return {
            "status": s.status.value,
            "current_task": s.current_task,
            "current_task_emoji": s.current_task_emoji,
            "progress": round(s.progress, 2),
            "tasks_completed": s.tasks_completed,
            "total_bonus_pts": s.total_bonus_pts,
            "task_history": s.task_history[-8:],
            "uptime": int(time.time() - s.started_at),
        }

    def get_stats(self) -> dict:
        return self.get_state()

    async def run_loop(self, broadcast: Callable):
        """
        Continuously pick tasks, work on them, then notify the player when done.
        """
        await asyncio.sleep(3)  # warm-up

        while True:
            try:
                # ── Pick a random task ──
                task = random.choice(TASKS)
                self._task = task
                duration = random.uniform(task.duration_min, task.duration_max)
                self._task_start = time.time()
                self._task_end = self._task_start + duration

                self.state.status = AgentStatus.WORKING
                self.state.current_task = task.name
                self.state.current_task_emoji = task.emoji
                self.state.progress = 0.0

                await broadcast({"type": "agent_state", **self.get_state()})

                # ── Progress updates every 2s ──
                while time.time() < self._task_end:
                    await asyncio.sleep(2)
                    elapsed = time.time() - self._task_start
                    self.state.progress = min(elapsed / duration, 1.0)
                    await broadcast({"type": "agent_state", **self.get_state()})

                # ── Task done! ──
                self.state.status = AgentStatus.DONE
                self.state.progress = 1.0
                self.state.tasks_completed += 1
                self.state.total_bonus_pts += task.bonus_pts
                self.state.task_history.append({
                    "task": task.name,
                    "emoji": task.emoji,
                    "pts": task.bonus_pts,
                    "time": int(time.time()),
                    "duration": round(duration, 1),
                })

                # Broadcast state + notification separately
                await broadcast({"type": "agent_state", **self.get_state()})
                await asyncio.sleep(0.2)
                await broadcast({
                    "type": "notification",
                    "title": f"{task.emoji} {task.name}",
                    "message": task.done_message,
                    "bonus_pts": task.bonus_pts,
                    "level": "success",
                    "duration": round(duration, 0),
                })

                # Rest before next task
                self.state.status = AgentStatus.IDLE
                self.state.current_task = ""
                self.state.current_task_emoji = ""
                self.state.progress = 0.0
                await broadcast({"type": "agent_state", **self.get_state()})

                rest = random.uniform(5, 20)
                await asyncio.sleep(rest)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Agent loop error: {e}")
                await asyncio.sleep(5)
