import asyncio

import pytest

from yoyo.application.commands import PerformTrick, StartTask
from yoyo.domain.errors import TrickOnCooldown


def test_failed_transaction_rolls_back_and_publishes_nothing(container):
    seen = []

    async def handler(event):
        seen.append(event)

    from yoyo.domain.events import DomainEvent
    container.bus.subscribe(DomainEvent, handler)

    async def scenario():
        await container.commands.perform_trick(PerformTrick("Sleeper"))
        before = len(seen)
        with pytest.raises(TrickOnCooldown):
            await container.commands.perform_trick(PerformTrick("Sleeper"))
        assert len(seen) == before                       # nothing published
        assert (await container.queries.get_stats()).score == 5  # score unchanged

    asyncio.run(scenario())


def test_concurrent_commands_are_serialized(container):
    async def scenario():
        await asyncio.gather(*(container.commands.start_task(StartTask(f"t{i}")) for i in range(20)))
        state = await container.queries.get_state()
        assert state.status == "WORKING"

    asyncio.run(scenario())
