"""WebSocket fan-out. Delivery is best-effort (at-most-once): a client that
fails to receive a message is dropped and resyncs from the snapshot it gets on
reconnect."""

import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketHub:
    def __init__(self) -> None:
        self._clients: list[WebSocket] = []

    @property
    def size(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)
        logger.info("Client connected. Total: %d", self.size)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)
        logger.info("Client disconnected. Total: %d", self.size)

    async def broadcast(self, data: dict) -> None:
        message = json.dumps(data)
        for client in list(self._clients):
            try:
                await client.send_text(message)
            except Exception:
                self.disconnect(client)
