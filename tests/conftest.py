import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from yoyo.api.app import create_app  # noqa: E402
from yoyo.application.ports import Clock  # noqa: E402
from yoyo.container import build_container  # noqa: E402
from yoyo.settings import Settings  # noqa: E402


class FakeClock(Clock):
    def __init__(self, start: float = 1000.0):
        self.t = start

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def container(clock):
    return build_container(Settings(external_task_ttl=90, cache_ttl=1.0), clock, random.Random(1))


@pytest.fixture
def app(container):
    return create_app(container)
