"""Wire YoYo Dev into Claude, for every project (not just this folder).

    python src/claude_setup.py install [--dry-run]
    python src/claude_setup.py uninstall
    YoYoDev.exe --install-claude / --uninstall-claude

What it touches (idempotent, backs up each file once as *.yoyo-backup):
  * ~/.claude/settings.json  -> user-level Claude Code hooks. Each hook is a bare
    ``curl`` forwarding the hook JSON to the game, so it needs no Python, adds a
    few ms, and silently does nothing when the game is closed.
  * Claude Desktop's claude_desktop_config.json -> the ``yoyo-dev`` MCP server
    (only if Claude Desktop's config folder exists).
"""

import json
import os
import shutil
import sys
from pathlib import Path

GAME_URL = os.environ.get("YOYO_URL", "http://127.0.0.1:8000")
MARKER = "/api/hooks/claude"
HOOK_EVENTS = ("UserPromptSubmit", "PreToolUse", "Stop")
SERVER_NAME = "yoyo-dev"


def hook_command() -> str:
    return (f'curl -s --connect-timeout 0.2 -m 1 -X POST -H "Content-Type: application/json" '
            f'--data-binary @- {GAME_URL}{MARKER} >/dev/null 2>&1 || true')


def mcp_entry() -> dict:
    if getattr(sys, "frozen", False):
        command, args = sys.executable, ["--mcp"]
    else:
        command, args = sys.executable, [str(Path(__file__).resolve().parent / "mcp_server.py")]
    return {"command": command, "args": args,
            "env": {"YOYO_URL": GAME_URL, "YOYO_AUTOSTART": "1"}}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else {}


def _save(path: Path, data: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + ".yoyo-backup")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {path}")


def _is_ours(group: dict) -> bool:
    return any(MARKER in h.get("command", "") for h in group.get("hooks", []))


def claude_code_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def desktop_config_paths() -> list[Path]:
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Claude")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        for pkg in Path(local, "Packages").glob("Claude_*"):
            candidates.append(pkg / "LocalCache" / "Roaming" / "Claude")
    return [d / "claude_desktop_config.json" for d in candidates if d.is_dir()]


def install(dry_run: bool = False) -> None:
    path = claude_code_settings_path()
    data = _load(path)
    hooks = data.setdefault("hooks", {})
    for event in HOOK_EVENTS:
        groups = hooks.setdefault(event, [])
        groups[:] = [g for g in groups if not _is_ours(g)]
        groups.append({"hooks": [{"type": "command", "command": hook_command(), "timeout": 3}]})
    _save(path, data, dry_run)

    configs = desktop_config_paths()
    if not configs:
        print("Claude Desktop config folder not found — skipped MCP registration there.")
    for cfg_path in configs:
        cfg = _load(cfg_path)
        cfg.setdefault("mcpServers", {})[SERVER_NAME] = mcp_entry()
        _save(cfg_path, cfg, dry_run)


def uninstall(dry_run: bool = False) -> None:
    path = claude_code_settings_path()
    if path.exists():
        data = _load(path)
        hooks = data.get("hooks", {})
        for event in list(hooks):
            hooks[event] = [g for g in hooks[event] if not _is_ours(g)]
            if not hooks[event]:
                del hooks[event]
        if not hooks:
            data.pop("hooks", None)
        _save(path, data, dry_run)
    for cfg_path in desktop_config_paths():
        cfg = _load(cfg_path)
        if cfg.get("mcpServers", {}).pop(SERVER_NAME, None) is not None:
            _save(cfg_path, cfg, dry_run)


def main(argv: list[str]) -> int:
    action = argv[0] if argv else "install"
    dry = "--dry-run" in argv
    if action == "install":
        install(dry)
    elif action == "uninstall":
        uninstall(dry)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
