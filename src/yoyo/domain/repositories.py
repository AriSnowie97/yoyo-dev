"""Repository port — the domain's view of persistence."""

from abc import ABC, abstractmethod

from .agent import YoYoAgent


class AgentRepository(ABC):
    """There is exactly one agent per server, so the repository is a singleton store."""

    @abstractmethod
    async def get(self) -> YoYoAgent: ...

    @abstractmethod
    async def save(self, agent: YoYoAgent) -> None: ...
