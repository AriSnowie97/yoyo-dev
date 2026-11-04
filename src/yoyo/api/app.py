"""FastAPI application factory: routes are thin adapters over the services."""

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..application import mappers
from ..container import Container, build_container
from ..domain.errors import (
    DomainError,
    InvalidValue,
    NoActiveTask,
    TrickOnCooldown,
    UnknownTrick,
)
from .schemas import (
    NotifyRequest,
    StartTaskRequest,
    TrackerRequest,
    TrickRequest,
    UpdateTaskRequest,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ERROR_STATUS: dict[type[DomainError], int] = {
    InvalidValue: 422,
    UnknownTrick: 422,
    NoActiveTask: 409,
    TrickOnCooldown: 429,
}


def get_container(request: Request) -> Container:
    return request.app.state.container


def _static_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "static"
    return Path(__file__).resolve().parents[3] / "static"


def create_app(container: Container | None = None) -> FastAPI:
    container = container or build_container()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(container.worker.run())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(title="YoYo Dev v3", lifespan=lifespan)
    app.state.container = container

    static_path = _static_dir()
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError):
        status = next((s for t, s in ERROR_STATUS.items() if isinstance(exc, t)), 400)
        return JSONResponse(status_code=status, content={"error": str(exc), "code": type(exc).__name__})

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse((static_path / "index.html").read_text(encoding="utf-8"))

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/status")
    async def agent_status(c: Container = Depends(get_container)):
        return mappers.state_to_status_view(await c.queries.get_state())

    @app.get("/api/stats")
    async def get_stats(c: Container = Depends(get_container)):
        return asdict(await c.queries.get_stats())

    @app.post("/api/task/start")
    async def task_start(body: StartTaskRequest, c: Container = Depends(get_container)):
        await c.commands.start_task(body.to_command())
        return {"ok": True}

    @app.post("/api/task/update")
    async def task_update(body: UpdateTaskRequest, c: Container = Depends(get_container)):
        """Live step update — shows what the AI agent is doing right now."""
        await c.commands.update_task(body.to_command())
        return {"ok": True}

    @app.post("/api/task/stop")
    async def task_stop(c: Container = Depends(get_container)):
        await c.commands.complete_task()
        return {"ok": True}

    @app.post("/api/reset")
    async def reset_agent(c: Container = Depends(get_container)):
        await c.commands.reset()
        return {"status": "ok"}

    @app.post("/api/trick")
    async def perform_trick(body: TrickRequest, c: Container = Depends(get_container)):
        return asdict(await c.commands.perform_trick(body.to_command()))

    @app.post("/api/notify")
    async def post_notification(body: NotifyRequest, c: Container = Depends(get_container)):
        await c.commands.notify(body.to_command())
        return {"ok": True}

    @app.post("/api/tracker")
    async def update_tracker(body: TrackerRequest, c: Container = Depends(get_container)):
        """Called by ai_tracker.py whenever the active window changes."""
        changed = await c.commands.report_tracker(body.to_command())
        return {"status": "ok", "changed": changed}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        c: Container = websocket.app.state.container
        await c.hub.connect(websocket)
        # full snapshot on connect, so a reconnecting client always resyncs
        await websocket.send_text(json.dumps(mappers.state_to_wire(await c.queries.get_state())))
        try:
            while True:
                if await websocket.receive_text() == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            c.hub.disconnect(websocket)

    return app
