# YoYo Dev 🪀

> AI agent plays yo-yo while it works — real-time 8-bit animation powered by Python + FastAPI + WebSockets

![Status](https://img.shields.io/badge/status-live-brightgreen)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-enabled-purple)

## Features

- 🪀 **8-bit pixel art yo-yo** animated in HTML Canvas
- 🤖 **Autonomous AI agent** that automatically performs tasks and tricks
- ⚡ **Real-time WebSocket** updates — no page refresh needed
- 🖥️ **Native Desktop App** — beautifully wrapped using `pywebview` in a standalone `.exe`
- 👀 **User Activity Tracker** — automatically detects if you are using an IDE (VS Code, Cursor) or AI Web Interface (Claude, ChatGPT) and streams it to the HUD
- 🎮 **6+ tricks** with scoring (Walk the Dog, Around the World, etc.)
- 🔌 **MCP Server** — Claude Desktop and other AI agents can control the yo-yo
- 🚂 **Railway-ready** — deploy 24/7 in one click

## Quick Start

### For Windows Users
Simply double-click the **`YoYoDev.exe`** file! It will automatically start the background server, initialize the AI tracker, and open the game in a clean, native desktop window.

### For Developers
```bash
git clone <your-repo>
cd yoyo-dev
pip install -r requirements.txt

# Run the native desktop launcher (starts server + tracker + webview)
python src/launcher.py

# OR run the server directly (no tracker/native window)
uvicorn src.main:app --reload
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
| POST | `/api/tracker`   | Update user activity state `{"state": "..."}` |
| POST | `/api/reset`     | Reset agent |
| WS   | `/ws`            | WebSocket state stream |

## MCP Integration

Connect from Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "yoyo-dev": {
      "command": "python",
      "args": ["path/to/yoyo-dev/mcp_server.py"],
      "env": {
        "YOYO_URL": "http://127.0.0.1:8000"
      }
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
4. Done! Railway uses `Procfile` + `railway.toml` pointing to `src.main:app`

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
