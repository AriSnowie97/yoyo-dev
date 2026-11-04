"""
MCP Server 🤖 — lets Claude (Desktop / Code) drive the YoYo Dev game.

Design (see docs/ARCHITECTURE.md, "Distributed trade-offs"):
  * The game is *telemetry for fun*, never a dependency of Claude's real work:
    every call is best-effort, has a short timeout and never raises. If the
    game is not running, tools answer with a hint and Claude simply continues.
  * After a failed call the gateway backs off for a few seconds (poor man's
    circuit breaker) so a dead game costs Claude almost nothing.
  * Optional ``YOYO_AUTOSTART=1`` starts the game the first time Claude
    reports something while it is down.

Run standalone: python src/mcp_server.py
"""

import asyncio
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

import httpx

try:
    from mcp import types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

BASE_URL = os.environ.get("YOYO_URL", "http://localhost:8000")
AUTOSTART = os.environ.get("YOYO_AUTOSTART", "") not in ("", "0", "false")
REQUEST_TIMEOUT = 2.0
BACKOFF_SECONDS = 8.0
ROOT = Path(__file__).resolve().parent.parent

INSTRUCTIONS = (
    "YoYo Dev is a small retro yo-yo game the user plays while you work. "
    "Keep it informed so the game mirrors your REAL progress: call `update_task` "
    "when you start each meaningful step (reading, editing, testing...) with a short "
    "label and progress 0-1, and call `notify` (with some bonus_pts) when you finish a "
    "major piece of work. Use `get_status` to see whether the user is currently playing "
    "(player_present) — if they are, prefer concise progress labels so they can follow. "
    "All YoYo tools are best-effort: if one says the game is not running, ignore it and "
    "carry on with the user's actual task."
)


class GameGateway:
    """Best-effort HTTP client for the game server."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._down_until = 0.0
        self._autostart_tried = False

    async def call(self, method: str, path: str, json: dict | None = None) -> tuple[int, dict] | None:
        """Returns (status, body) or None when the game is unreachable."""
        if time.monotonic() < self._down_until:
            return None
        try:
            return await self._request(method, path, json)
        except httpx.HTTPError:
            if AUTOSTART and not self._autostart_tried and self._is_local():
                self._autostart_tried = True
                if await self._start_game():
                    try:
                        return await self._request(method, path, json)
                    except httpx.HTTPError:
                        pass
            self._down_until = time.monotonic() + BACKOFF_SECONDS
            return None

    async def _request(self, method: str, path: str, json: dict | None) -> tuple[int, dict]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=REQUEST_TIMEOUT) as client:
            resp = await client.request(method, path, json=json)
        try:
            body = resp.json()
        except ValueError:
            body = {}
        return resp.status_code, body

    def _is_local(self) -> bool:
        return urlparse(self._base_url).hostname in ("localhost", "127.0.0.1")

    async def _start_game(self) -> bool:
        """Launch the game (native window if pywebview exists, else browser tab)."""
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        quiet = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, creationflags=flags, cwd=str(ROOT))
        try:
            try:
                import webview  # noqa: F401
                subprocess.Popen([sys.executable, str(ROOT / "src" / "launcher.py")], **quiet)
                browser = False
            except ImportError:
                subprocess.Popen([sys.executable, str(ROOT / "src" / "main.py")], **quiet)
                subprocess.Popen([sys.executable, str(ROOT / "src" / "ai_tracker.py")], **quiet)
                browser = True
        except OSError:
            return False
        for _ in range(20):
            await asyncio.sleep(0.5)
            try:
                await self._request("GET", "/health", None)
                if browser:
                    webbrowser.open(self._base_url)
                return True
            except httpx.HTTPError:
                continue
        return False


gateway = GameGateway(BASE_URL)

OFFLINE = (
    "🪀 YoYo Dev is not running right now — skipped. This is optional; "
    "continue with the user's task. (The user can start YoYoDev.exe.)"
)


def _problem(status: int, body: dict) -> str:
    detail = body.get("error") or body.get("detail") or body
    return f"⚠️ YoYo rejected the request ({status}): {detail}"


async def _post(path: str, payload: dict | None = None) -> tuple[bool, str, dict]:
    result = await gateway.call("POST", path, payload or {})
    if result is None:
        return False, OFFLINE, {}
    status, body = result
    if status >= 400:
        return False, _problem(status, body), body
    return True, "", body


async def handle_update_task(args: dict) -> str:
    payload = {"task_name": args.get("task", "Working…"), "emoji": args.get("emoji", "⚙️")}
    if "progress" in args:
        payload["progress"] = float(args["progress"])
    ok, msg, _ = await _post("/api/task/update", payload)
    if not ok:
        return msg
    pct = f" ({int(payload.get('progress', 0) * 100)}%)" if "progress" in payload else ""
    return f"🪀 Task updated: {payload['emoji']} {payload['task_name']}{pct}"


async def handle_notify(args: dict) -> str:
    payload = {
        "title": args.get("title", "✅ Done"),
        "message": args.get("message", ""),
        "bonus_pts": int(args.get("bonus_pts", 0)),
        "level": args.get("level", "success"),
    }
    ok, msg, _ = await _post("/api/notify", payload)
    return f"🔔 Notification sent: {payload['title']}" if ok else msg


async def handle_set_agent_status(args: dict) -> str:
    status = args.get("status", "IDLE")
    if status == "WORKING":
        ok, msg, _ = await _post("/api/task/start", {"task_name": args.get("task_name") or "Working…"})
    elif status == "DONE":
        ok, msg, _ = await _post("/api/task/stop")
    else:
        ok, msg, _ = await _post("/api/reset")
    return f"✅ Status set to {status}" if ok else msg


async def handle_perform_trick(args: dict) -> str:
    ok, msg, body = await _post("/api/trick", {"trick_name": args.get("trick_name", "")})
    if not ok:
        return msg
    return f"🪀 Performed '{body.get('trick')}' (+{body.get('points', 0)} pts). Total score: {body.get('score', 0)}"


async def handle_get_stats(args: dict) -> str:
    result = await gateway.call("GET", "/api/stats")
    if result is None:
        return OFFLINE
    d = result[1]
    return (
        "📊 YoYo Stats:\n"
        f"  Score: {d.get('score', 0)} pts\n"
        f"  Tricks done: {d.get('tricks_done', 0)}\n"
        f"  Tasks completed: {d.get('tasks_completed', 0)}\n"
        f"  Uptime: {d.get('uptime_seconds', 0)}s"
    )


async def handle_get_status(args: dict) -> str:
    result = await gateway.call("GET", "/api/status")
    if result is None:
        return OFFLINE
    d = result[1]
    playing = "yes — the user is in the game window right now" if d.get("player_present") else "no"
    return (
        f"🤖 Agent status: {d.get('status', 'IDLE')}, task: '{d.get('current_task') or 'none'}', "
        f"score: {d.get('score', 0)}\n"
        f"🎮 Player present: {playing}\n"
        f"👀 User is looking at: {d.get('tracker_detail') or d.get('tracker_state', 'IDLE')}"
    )


TOOL_HANDLERS = {
    "update_task": handle_update_task,
    "notify": handle_notify,
    "set_agent_status": handle_set_agent_status,
    "perform_trick": handle_perform_trick,
    "get_stats": handle_get_stats,
    "get_status": handle_get_status,
}

if MCP_AVAILABLE:
    TRICKS = ["Sleeper", "Walk the Dog", "Rock the Baby", "Around the World",
              "Loop the Loop", "Eiffel Tower", "Atom Smasher", "String Burn"]

    TOOLS = [
        types.Tool(
            name="update_task",
            description=(
                "Show the user what you are doing RIGHT NOW in the YoYo Dev game HUD. "
                "Call at the start of each meaningful step (e.g. 'Reading files', "
                "'Editing main.py', 'Running tests'). Cheap and safe to call often."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "maxLength": 120,
                             "description": "Short label, e.g. 'Editing yoyo_agent.py'"},
                    "emoji": {"type": "string", "description": "Emoji, e.g. '✏️', '🔍', '🧪'. Optional."},
                    "progress": {"type": "number", "minimum": 0.0, "maximum": 1.0,
                                 "description": "Progress 0.0–1.0 of the overall job."},
                },
                "required": ["task"],
            },
        ),
        types.Tool(
            name="notify",
            description="Pop a notification (and award bonus points) in the game when a major piece of work is done.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short title, e.g. '✅ Tests green'"},
                    "message": {"type": "string", "description": "What was accomplished"},
                    "bonus_pts": {"type": "integer", "minimum": 0, "maximum": 500,
                                  "description": "Bonus points for the player (0–500)"},
                    "level": {"type": "string", "enum": ["success", "info", "warning", "error"]},
                },
                "required": ["title", "message"],
            },
        ),
        types.Tool(
            name="set_agent_status",
            description="Set the game's agent status: WORKING when you start a job, DONE when finished, IDLE to reset.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["IDLE", "WORKING", "DONE"]},
                    "task_name": {"type": "string", "description": "Task label (for WORKING)"},
                },
                "required": ["status"],
            },
        ),
        types.Tool(
            name="perform_trick",
            description="Make the yo-yo perform a trick (earns points). Use sparingly, e.g. as a small celebration.",
            inputSchema={
                "type": "object",
                "properties": {"trick_name": {"type": "string", "enum": TRICKS}},
                "required": ["trick_name"],
            },
        ),
        types.Tool(
            name="get_stats",
            description="Get the game's statistics (score, tricks, completed tasks, uptime).",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_status",
            description="Get the game's state, including whether the user is currently playing it.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]

    server = Server("yoyo-dev", instructions=INSTRUCTIONS)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            text = f"❌ Unknown tool: {name}"
        else:
            try:
                text = await handler(arguments or {})
            except (TypeError, ValueError) as exc:  # bad argument types from the model
                text = f"⚠️ Invalid arguments for {name}: {exc}"
        return [types.TextContent(type="text", text=text)]


async def main():
    if not MCP_AVAILABLE:
        print("❌ MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
