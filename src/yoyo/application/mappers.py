"""Mapping between the three model families:

    domain aggregate  ->  DTO (read model)  ->  wire dict (REST / WebSocket)

Each arrow lives in exactly one function, so the data model can change on one
side without touching the others.
"""

from dataclasses import asdict

from ..domain.agent import YoYoAgent
from ..domain.events import NotificationRaised, TrackerChanged, TrickPerformed
from .dto import AgentStateDTO, StatsDTO

# Wire message types understood by static/app.js
AGENT_STATE = "agent_state"
TASK_LOG = "task_log"
DO_TRICK = "do_trick"
NOTIFICATION = "notification"
TRACKER_UPDATE = "tracker_update"


def agent_to_state_dto(agent: YoYoAgent, now: float) -> AgentStateDTO:
    return AgentStateDTO(
        status=agent.status.value,
        current_task=agent.task.name if agent.task else "",
        current_task_emoji=agent.task.emoji if agent.task else "",
        progress=round(agent.progress.value, 2),
        task_source=agent.source.value if agent.source else "",
        tasks_completed=agent.tasks_completed,
        total_bonus_pts=agent.total_bonus_pts,
        score=agent.score,
        tricks_done=agent.tricks_done,
        uptime=int(now - agent.started_at),
        task_history=list(agent.history[-8:]),
        tracker_state=agent.tracker.state.value,
        tracker_detail=agent.tracker.detail,
        tracker_emoji=agent.tracker.emoji,
        tracker_title=agent.tracker.window_title,
        tracker_process=agent.tracker.process,
        player_present=agent.player_present,
    )


def agent_to_stats_dto(agent: YoYoAgent, now: float) -> StatsDTO:
    return StatsDTO(
        score=agent.score,
        tricks_done=agent.tricks_done,
        tasks_completed=agent.tasks_completed,
        total_bonus_pts=agent.total_bonus_pts,
        uptime_seconds=int(now - agent.started_at),
    )


def state_to_wire(dto: AgentStateDTO) -> dict:
    return {"type": AGENT_STATE, **asdict(dto)}


def state_to_status_view(dto: AgentStateDTO) -> dict:
    """GET /api/status keeps its historical aliases for older clients."""
    return {**asdict(dto), "task_name": dto.current_task}


def task_log_to_wire(dto: AgentStateDTO) -> dict:
    return {
        "type": TASK_LOG,
        "task": dto.current_task,
        "emoji": dto.current_task_emoji,
        "progress": dto.progress,
    }


def trick_to_wire(event: TrickPerformed) -> dict:
    return {"type": DO_TRICK, "trick_id": event.trick_id, "pts": event.points}


def notification_to_wire(event: NotificationRaised) -> dict:
    return {
        "type": NOTIFICATION,
        "title": event.title,
        "message": event.message,
        "bonus_pts": event.bonus_pts,
        "level": event.level,
        "duration": event.duration,
    }


def tracker_to_wire(event: TrackerChanged) -> dict:
    return {
        "type": TRACKER_UPDATE,
        "state": event.state,
        "detail": event.detail,
        "emoji": event.emoji,
        "window_title": event.window_title,
        "process": event.process,
    }
