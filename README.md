# YoYo Dev 🪀

> AI agent plays yo-yo while it works — real-time 8-bit animation powered by Python + FastAPI + WebSockets

![Status](https://img.shields.io/badge/status-live-brightgreen)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-enabled-purple)

## Features

- 🪀 **8-bit pixel art yo-yo** animated in HTML Canvas
- 🤖 **Autonomous AI agent** that automatically performs tasks and tricks
- ⚡ **Real-time WebSocket** updates — no page refresh needed
- 🎮 **6+ tricks** with scoring (Walk the Dog, Around the World, etc.)
- 🔌 **MCP Server** — Claude Desktop and other AI agents can control the yo-yo
- 🚂 **Railway-ready** — deploy 24/7 in one click

## Quick Start

```bash
git clone <your-repo>
cd yoyo-dev
pip install -r requirements.txt
uvicorn main:app --reload
# Open http://localhost:8000
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/`              | Main app page |
| GET  | `/health`        | Health check |
| GET  | `/api/status`    | Current agent state |
| GET  | `/api/stats`     | Score + trick history |
| POST | `/api/task/start`| Start a task `{"task_name": "..."}` |
| POST | `/api/task/stop` | Complete current task |
| POST | `/api/trick`     | Perform a trick `{"trick_name": "..."}` |
| POST | `/api/reset`     | Reset agent |
| WS   | `/ws`            | WebSocket state stream |

## MCP Integration

Connect from Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "yoyo-dev": {
      "command": "python",
      "args": ["path/to/yoyo-dev/mcp_server.py"]
    }
  }
}
```

Available MCP tools:
- `set_agent_status(status, task_name)` — IDLE / WORKING / DONE
- `perform_trick(trick_name)` — earn points!
- `get_stats()` — score, tricks, uptime
- `get_status()` — current state

## Deploy to Railway

1. Push code to GitHub
2. Create new project on [railway.app](https://railway.app)
3. Connect GitHub repo → Railway auto-detects Python
4. Done! Railway uses `Procfile` + `railway.toml`

## Tricks & Points

| Trick | Points |
|-------|--------|
| Sleeper | 5 |
| Walk the Dog | 10 |
| Rock the Baby | 15 |
| Around the World | 25 |
| Loop the Loop | 30 |
| Eiffel Tower | 35 |
| Atom Smasher | 45 |
| String Burn | 50 |
