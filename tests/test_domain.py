import random

import pytest

from yoyo.domain.agent import YoYoAgent, TrackerSnapshot
from yoyo.domain.errors import InvalidValue, NoActiveTask, TrickOnCooldown, UnknownTrick
from yoyo.domain.events import NotificationRaised, TrickPerformed
from yoyo.domain.value_objects import (
    AgentStatus, BonusPoints, NotificationLevel, Progress, TaskLabel, TrackerState, Trick,
)


def make_agent() -> YoYoAgent:
    return YoYoAgent(started_at=0.0)


def test_value_objects_validate():
    with pytest.raises(InvalidValue):
        Progress(1.5)
    with pytest.raises(InvalidValue):
        TaskLabel("   ")
    with pytest.raises(InvalidValue):
        BonusPoints(501)
    assert TaskLabel("  hi ").name == "hi"
    with pytest.raises(UnknownTrick):
        Trick.by_title("Nope")


def test_complete_requires_running_task():
    with pytest.raises(NoActiveTask):
        make_agent().complete_task(now=1)


def test_task_lifecycle_counts_once():
    a = make_agent()
    a.start_task(TaskLabel("Edit", "✏️"), now=1)
    a.complete_task(now=2)
    assert a.status == AgentStatus.DONE and a.tasks_completed == 1


def test_trick_awards_points_and_has_cooldown():
    a = make_agent()
    a.perform_trick(Trick.EIFFEL_TOWER, now=10)
    assert a.score == 35
    with pytest.raises(TrickOnCooldown):
        a.perform_trick(Trick.SLEEPER, now=10.1)
    a.perform_trick(Trick.SLEEPER, now=11)
    assert a.score == 40
    assert sum(isinstance(e, TrickPerformed) for e in a.pull_events()) == 2


def test_stale_external_task_is_dropped_but_live_one_survives():
    a = make_agent()
    a.start_task(TaskLabel("Claude step"), now=0)
    rng = random.Random(0)
    a.tick(now=60, rng=rng, external_ttl=90)
    assert a.status == AgentStatus.WORKING
    a.tick(now=91, rng=rng, external_ttl=90)
    assert a.status == AgentStatus.IDLE


def test_external_task_beats_tracker_chunk():
    a = make_agent()
    a.change_tracker(TrackerSnapshot(TrackerState.IDE, "main.py", "💻"))
    a.start_task(TaskLabel("Real work"), now=0)
    a.tick(now=5, rng=random.Random(0), external_ttl=90)
    assert a.task.name == "Real work"


def test_tracker_chunk_finishes_with_reward():
    a = make_agent()
    rng = random.Random(0)
    a.change_tracker(TrackerSnapshot(TrackerState.AI_WEB, "Claude Desktop", "🤖"))
    t = 0.0
    while t < 60 and a.tasks_completed == 0:
        a.tick(now=t, rng=rng, external_ttl=90)
        t += 2
    assert a.tasks_completed == 1 and a.total_bonus_pts > 0
    assert any(isinstance(e, NotificationRaised) for e in a.pull_events())


def test_player_presence():
    a = make_agent()
    assert not a.player_present
    a.change_tracker(TrackerSnapshot(TrackerState.PLAYING))
    assert a.player_present
    a.notify("t", "m", BonusPoints(5), NotificationLevel.INFO)
    assert a.total_bonus_pts == 5
