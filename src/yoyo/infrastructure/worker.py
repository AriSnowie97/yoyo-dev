"""Background loop that keeps time-based behaviour of the agent moving."""

import asyncio
import logging

from ..application.services import GameCommandService

logger = logging.getLogger(__name__)


class ActivityWorker:
    def __init__(self, commands: GameCommandService, interval: float, warmup: float) -> None:
        self._commands = commands
        self._interval = interval
        self._warmup = warmup

    async def run(self) -> None:
        await asyncio.sleep(self._warmup)
        while True:
            try:
                await self._commands.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Agent tick failed")
                await asyncio.sleep(5)
            await asyncio.sleep(self._interval)
