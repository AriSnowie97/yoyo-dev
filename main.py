"""
YoYo Dev v2 🪀 — Main FastAPI Application
User plays yo-yo, AI agent sends notifications when tasks complete!
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from yoyo_agent import YoYoAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

agent = YoYoAgent()
connected_clients: list[WebSocket] = []


async def broadcast(data: dict):
    """Broadcast to all connected WebSocket clients."""
    message = json.dumps(data)
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)
    for c in disconnected:
        if c in connected_clients:
            connected_clients.remove(c)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(agent.run_loop(broadcast))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="YoYo Dev v2", lifespan=lifespan)

static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=(static_path / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/agent/status")
async def agent_status():
    return agent.get_state()


@app.post("/api/notify")
async def post_notification(body: dict):
    """External endpoint — AI agents call this to push notifications to the player."""
    notif = {
        "type": "notification",
        "title": body.get("title", "✅ Done"),
        "message": body.get("message", ""),
        "bonus_pts": int(body.get("bonus_pts", 0)),
        "level": body.get("level", "success"),   # success | info | warning | error
    }
    await broadcast(notif)
    return {"ok": True}


@app.get("/api/stats")
async def get_stats():
    return agent.get_stats()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"Client connected. Total: {len(connected_clients)}")

    # Send current agent state on connect
    await websocket.send_text(json.dumps({
        "type": "agent_state",
        **agent.get_state(),
    }))

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(connected_clients)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
