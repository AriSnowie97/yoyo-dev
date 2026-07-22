"""
YoYo Dev v2 🪀 — Main FastAPI Application
User plays yo-yo, AI agent sends notifications when tasks complete!
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from yoyo_agent import YoYoAgent, AgentStatus

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


import sys

app = FastAPI(title="YoYo Dev v2", lifespan=lifespan)

if getattr(sys, 'frozen', False):
    base_dir = Path(sys.executable).parent
else:
    base_dir = Path(__file__).parent.parent

static_path = base_dir / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=(static_path / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/status")
async def agent_status():
    state = agent.get_state()
    return {
        "status": state["status"],
        "task_name": state["current_task"],
        "score": agent.state.score,
        "tricks_done": agent.state.tricks_done,
        **state
    }


@app.post("/api/task/start")
async def task_start(body: dict):
    agent.state.status = AgentStatus.WORKING
    agent.state.current_task = body.get("task_name", "External Task")
    agent.state.current_task_emoji = body.get("emoji", "🤖")
    agent.state.progress = 0.0
    await broadcast({"type": "agent_state", **agent.get_state()})
    return {"ok": True}


@app.post("/api/task/update")
async def task_update(body: dict):
    """Live task update — call this mid-task to show current step in UI."""
    agent.state.status = AgentStatus.WORKING
    agent.state.current_task = body.get("task_name", agent.state.current_task)
    agent.state.current_task_emoji = body.get("emoji", agent.state.current_task_emoji or "⚙️")
    agent.state.progress = float(body.get("progress", agent.state.progress))
    await broadcast({"type": "agent_state", **agent.get_state()})
    # Also log it
    await broadcast({
        "type":    "task_log",
        "task":    agent.state.current_task,
        "emoji":   agent.state.current_task_emoji,
        "progress": agent.state.progress,
    })
    return {"ok": True}


@app.post("/api/task/stop")
async def task_stop():
    agent.state.status = AgentStatus.DONE
    agent.state.progress = 1.0
    agent.state.tasks_completed += 1
    await broadcast({"type": "agent_state", **agent.get_state()})
    return {"ok": True}


@app.post("/api/reset")
async def reset_agent():
    agent.reset()
    await broadcast({"type": "agent_state", **agent.get_state()})
    return {"status": "ok"}


TRICK_MAPPING = {
    "Sleeper":          ("sleeper",  5),
    "Walk the Dog":     ("walkdog",  10),
    "Rock the Baby":    ("rockbaby", 15),
    "Around the World": ("around",   25),
    "Loop the Loop":    ("loop",     30),
    "Eiffel Tower":     ("eiffel",   35),
    "Atom Smasher":     ("atom",     45),
    "String Burn":      ("string",   50),
}


@app.post("/api/trick")
async def perform_trick(body: dict):
    trick_name = body.get("trick_name")
    if trick_name not in TRICK_MAPPING:
        return {"error": "Unknown trick"}

    trick_id, pts = TRICK_MAPPING[trick_name]
    agent.state.score += pts
    agent.state.tricks_done += 1

    await broadcast({"type": "do_trick", "trick_id": trick_id, "pts": pts})
    return {"trick": trick_name, "points": pts, "score": agent.state.score}


@app.post("/api/notify")
async def post_notification(body: dict):
    """External endpoint — AI agents call this to push notifications to the player."""
    notif = {
        "type":      "notification",
        "title":     body.get("title", "✅ Done"),
        "message":   body.get("message", ""),
        "bonus_pts": int(body.get("bonus_pts", 0)),
        "level":     body.get("level", "success"),  # success | info | warning | error
    }
    await broadcast(notif)
    return {"ok": True}


@app.post("/api/tracker")
async def update_tracker(request: Request):
    """
    Called by ai_tracker.py every time the active window changes.
    Payload: { state, detail, window_title }
    """
    data         = await request.json()
    state        = data.get("state", "IDLE")
    detail       = data.get("detail", "")
    window_title = data.get("window_title", "")

    changed = agent.set_tracker_state(state, detail, window_title)

    # Always broadcast so the UI badge updates in real time
    await broadcast({
        "type":         "tracker_update",
        "state":        state,
        "detail":       detail,
        "window_title": window_title,
    })

    return {"status": "ok", "changed": changed}


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
