import time

from ..application.ports import Clock


class SystemClock(Clock):
    def now(self) -> float:
        return time.time()
