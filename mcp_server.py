"""
MCP Server 🤖 — Model Context Protocol server for YoYo Dev.
Allows external AI agents (Claude Desktop, etc.) to control the yo-yo.

Run standalone: python mcp_server.py
"""

import asyncio
import sys
import httpx

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

BASE_URL = "http://localhost:8000"

if MCP_AVAILABLE:
    server = Server("yoyo-dev")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
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

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
            if name == "set_agent_status":
                status = arguments.get("status", "IDLE")
                task_name = arguments.get("task_name", "")

                if status == "WORKING":
                    resp = await client.post("/api/task/start", json={"task_name": task_name})
                elif status == "DONE":
                    resp = await client.post("/api/task/stop")
                else:
                    resp = await client.post("/api/reset")

                data = resp.json()
                return [types.TextContent(type="text", text=f"✅ Status set to {status}. Response: {data}")]

            elif name == "perform_trick":
                trick_name = arguments.get("trick_name")
                resp = await client.post("/api/trick", json={"trick_name": trick_name})
                data = resp.json()
                return [types.TextContent(
                    type="text",
                    text=f"🪀 Performed '{data.get('trick', 'trick')}' (+{data.get('points', 0)} pts). Total score: {data.get('score', 0)}"
                )]

            elif name == "get_stats":
                resp = await client.get("/api/stats")
                data = resp.json()
                return [types.TextContent(
                    type="text",
                    text=(
                        f"📊 YoYo Stats:\n"
                        f"  Score: {data['score']} pts\n"
                        f"  Tricks done: {data['tricks_done']}\n"
                        f"  Tasks completed: {data['tasks_completed']}\n"
                        f"  Uptime: {data['uptime_seconds']}s"
                    )
                )]

            elif name == "get_status":
                resp = await client.get("/api/status")
                data = resp.json()
                return [types.TextContent(
                    type="text",
                    text=f"🤖 Agent status: {data['status']}, Task: '{data.get('task_name', 'none')}', Score: {data['score']}"
                )]

            else:
                return [types.TextContent(type="text", text=f"❌ Unknown tool: {name}")]


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
