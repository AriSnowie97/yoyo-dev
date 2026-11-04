"""Translates Claude Code hook payloads into game commands.

The hook itself is a bare ``curl`` that forwards the hook JSON to the server,
so it needs no Python, works from any project, and the mapping lives here
where it is testable. Only tool names and file basenames are used — never
prompts or shell commands.
"""

import ntpath

from ..domain.errors import DomainError
from .commands import RaiseNotification, StartTask, UpdateTask
from .services import GameCommandService

# Claude can think for minutes between events; Stop ends the task explicitly.
HOOK_LEASE_SECONDS = 900.0

FILE_TOOLS = {"Read": ("📖", "Reading"), "Edit": ("✏️", "Editing"),
              "Write": ("✏️", "Writing"), "NotebookEdit": ("✏️", "Editing")}
OTHER_TOOLS = {"Bash": ("⌨️", "Running a command"), "PowerShell": ("⌨️", "Running a command"),
               "Grep": ("🔍", "Searching the code"), "Glob": ("🔍", "Looking for files"),
               "Agent": ("🧑‍🤝‍🧑", "Delegating to a sub-agent"),
               "WebSearch": ("🌐", "Searching the web"), "WebFetch": ("🌐", "Reading a web page")}


def describe_tool(tool: str, tool_input: dict) -> tuple[str, str] | None:
    if tool.startswith("mcp__yoyo"):
        return None  # Claude is already talking to the game directly
    if tool in FILE_TOOLS:
        emoji, verb = FILE_TOOLS[tool]
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        return emoji, f"{verb} {ntpath.basename(path.replace('/', chr(92)))}".strip()
    if tool in OTHER_TOOLS:
        return OTHER_TOOLS[tool]
    return "⚙️", f"Using {tool.split('__')[-1]}"[:100]


class ClaudeActivityService:
    def __init__(self, commands: GameCommandService) -> None:
        self._commands = commands

    async def report(self, event: dict) -> None:
        name = event.get("hook_event_name")
        if name == "UserPromptSubmit":
            await self._commands.start_task(
                StartTask("Claude is thinking…", "🤔", HOOK_LEASE_SECONDS))
        elif name == "PreToolUse":
            info = describe_tool(str(event.get("tool_name", "")), event.get("tool_input") or {})
            if info:
                await self._commands.update_task(
                    UpdateTask(name=info[1], emoji=info[0], lease=HOOK_LEASE_SECONDS))
        elif name == "Stop":
            try:
                await self._commands.complete_task()
            except DomainError:
                return  # nothing was running: not an error for a hook
            await self._commands.notify(RaiseNotification(
                "✅ Claude finished", "Your turn!", bonus_pts=25, level="success"))
