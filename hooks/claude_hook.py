"""Claude Code hook -> YoYo Dev.

Makes the game mirror Claude's real work automatically, without Claude having
to remember to call the MCP tools. Wired up in .claude/settings.json.

Never blocks or fails Claude: short timeout, all errors swallowed, exit 0.
Only tool *names* and file *basenames* are sent (never prompts or commands).
"""

import json
import os
import sys
import urllib.request

BASE_URL = os.environ.get("YOYO_URL", "http://localhost:8000")
TIMEOUT = 1.0

FILE_TOOLS = {"Read": ("📖", "Reading"), "Edit": ("✏️", "Editing"),
              "Write": ("✏️", "Writing"), "NotebookEdit": ("✏️", "Editing")}
OTHER_TOOLS = {"Bash": ("⌨️", "Running a command"), "PowerShell": ("⌨️", "Running a command"),
               "Grep": ("🔍", "Searching the code"), "Glob": ("🔍", "Looking for files"),
               "Agent": ("🧑‍🤝‍🧑", "Delegating to a sub-agent"),
               "WebSearch": ("🌐", "Searching the web"), "WebFetch": ("🌐", "Reading a web page")}


def post(path: str, payload: dict) -> None:
    req = urllib.request.Request(
        BASE_URL + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=TIMEOUT).close()
    except Exception:
        pass


def describe(tool: str, tool_input: dict) -> tuple[str, str] | None:
    if tool.startswith("mcp__yoyo"):
        return None  # Claude is already talking to the game directly
    if tool in FILE_TOOLS:
        emoji, verb = FILE_TOOLS[tool]
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        return emoji, f"{verb} {os.path.basename(path)}".strip()
    if tool in OTHER_TOOLS:
        emoji, label = OTHER_TOOLS[tool]
        return emoji, label
    return "⚙️", f"Using {tool.split('__')[-1]}"


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return
    name = event.get("hook_event_name")

    if name == "UserPromptSubmit":
        post("/api/task/start", {"task_name": "Claude is thinking…", "emoji": "🤔"})
    elif name == "PreToolUse":
        info = describe(event.get("tool_name", ""), event.get("tool_input") or {})
        if info:
            post("/api/task/update", {"task_name": info[1], "emoji": info[0]})
    elif name == "Stop":
        post("/api/task/stop", {})
        post("/api/notify", {"title": "✅ Claude finished", "message": "Your turn!",
                             "bonus_pts": 25, "level": "success"})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
