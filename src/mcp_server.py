"""
MCP Server 🤖 — Model Context Protocol server for YoYo Dev.
Allows external AI agents (Claude Desktop, etc.) to control the yo-yo.

Run standalone: python mcp_server.py
"""

import asyncio
import sys
import os
import httpx

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

BASE_URL = os.environ.get("YOYO_URL", "http://localhost:8000")

TOOLS = [
    types.Tool(
        name="update_task",
        description=(
            "Update the current task shown in YoYo Dev UI. "
            "Call this whenever you start a new step (e.g. 'Reading files', 'Editing main.py', 'Running tests'). "
            "This shows the user EXACTLY what you are doing right now."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Short task description shown in the UI (e.g. 'Editing yoyo_agent.py', 'Running unit tests')",
                },
                "emoji": {
                    "type": "string",
                    "description": "Emoji for the task (e.g. '✏️', '🔍', '🧪'). Optional.",
                },
                "progress": {
                    "type": "number",
                    "description": "Progress 0.0–1.0. Use 0.0 when starting, 1.0 when done.",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": ["task"],
        },
    ),
    types.Tool(
        name="notify",
        description="Send a completion notification to YoYo Dev when a major task is done.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title (e.g. '✅ Files updated')",
                },
                "message": {
                    "type": "string",
                    "description": "Details of what was accomplished",
                },
                "bonus_pts": {
                    "type": "integer",
                    "description": "Bonus points to award the player (0–500)",
                },
                "level": {
                    "type": "string",
                    "enum": ["success", "info", "warning", "error"],
                    "description": "Toast color/level",
                },
            },
            "required": ["title", "message"],
        },
    ),
    types.Tool(
        name="set_agent_status",
        description="Set the YoYo agent status. Use WORKING when you start a task, DONE when finished.",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["IDLE", "WORKING", "DONE"],
                    "description": "New agent status",
                },
                "task_name": {
                    "type": "string",
                    "description": "Human-readable task description (shown in UI)",
                },
            },
            "required": ["status"],
        },
    ),
    types.Tool(
        name="perform_trick",
        description="Make the yo-yo perform a trick! Earns points.",
        inputSchema={
            "type": "object",
            "properties": {
                "trick_name": {
                    "type": "string",
                    "enum": [
                        "Walk the Dog",
                        "Around the World",
                        "Rock the Baby",
                        "Sleeper",
                        "Loop the Loop",
                        "String Burn",
                        "Eiffel Tower",
                        "Atom Smasher",
                    ],
                    "description": "Name of the trick to perform",
                },
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_stats",
        description="Get current YoYo agent statistics (score, tricks done, uptime).",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_status",
        description="Get the current status of the YoYo agent.",
        inputSchema={"type": "object", "properties": {}},
    ),
]

if MCP_AVAILABLE:
    server = Server("yoyo-dev")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return TOOLS

    async def handle_update_task(client: httpx.AsyncClient, arguments: dict) -> str:
        task     = arguments.get("task", "Working…")
        emoji    = arguments.get("emoji", "⚙️")
        progress = float(arguments.get("progress", 0.0))
        await client.post("/api/task/update", json={
            "task_name": task,
            "emoji":     emoji,
            "progress":  progress,
        })
        return f"🪀 Task updated: {emoji} {task} ({int(progress*100)}%)"

    async def handle_notify(client: httpx.AsyncClient, arguments: dict) -> str:
        await client.post("/api/notify", json={
            "title":     arguments.get("title", "✅ Done"),
            "message":   arguments.get("message", ""),
            "bonus_pts": arguments.get("bonus_pts", 0),
            "level":     arguments.get("level", "success"),
        })
        return f"🔔 Notification sent: {arguments.get('title')}"

    async def handle_set_agent_status(client: httpx.AsyncClient, arguments: dict) -> str:
        status = arguments.get("status", "IDLE")
        task_name = arguments.get("task_name", "")

        if status == "WORKING":
            resp = await client.post("/api/task/start", json={"task_name": task_name})
        elif status == "DONE":
            resp = await client.post("/api/task/stop")
        else:
            resp = await client.post("/api/reset")

        data = resp.json()
        return f"✅ Status set to {status}. Response: {data}"

    async def handle_perform_trick(client: httpx.AsyncClient, arguments: dict) -> str:
        trick_name = arguments.get("trick_name")
        resp = await client.post("/api/trick", json={"trick_name": trick_name})
        data = resp.json()
        return f"🪀 Performed '{data.get('trick', 'trick')}' (+{data.get('points', 0)} pts). Total score: {data.get('score', 0)}"

    async def handle_get_stats(client: httpx.AsyncClient, arguments: dict) -> str:
        resp = await client.get("/api/stats")
        data = resp.json()
        return (
            f"📊 YoYo Stats:\n"
            f"  Score: {data.get('score', 0)} pts\n"
            f"  Tricks done: {data.get('tricks_done', 0)}\n"
            f"  Tasks completed: {data.get('tasks_completed', 0)}\n"
            f"  Uptime: {data.get('uptime_seconds', 0)}s"
        )

    async def handle_get_status(client: httpx.AsyncClient, arguments: dict) -> str:
        resp = await client.get("/api/status")
        data = resp.json()
        return f"🤖 Agent status: {data.get('status', 'IDLE')}, Task: '{data.get('task_name', 'none')}', Score: {data.get('score', 0)}"

    TOOL_HANDLERS = {
        "update_task": handle_update_task,
        "notify": handle_notify,
        "set_agent_status": handle_set_agent_status,
        "perform_trick": handle_perform_trick,
        "get_stats": handle_get_stats,
        "get_status": handle_get_status,
    }

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
            handler = TOOL_HANDLERS.get(name)
            if handler:
                result_text = await handler(client, arguments)
            else:
                result_text = f"❌ Unknown tool: {name}"
            
            return [types.TextContent(type="text", text=result_text)]


async def main():
    if not MCP_AVAILABLE:
        print("❌ MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
