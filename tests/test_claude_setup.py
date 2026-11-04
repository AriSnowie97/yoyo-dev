import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import claude_setup  # noqa: E402


def test_install_is_idempotent_preserves_foreign_hooks_and_uninstalls(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    desktop = tmp_path / "claude_desktop_config.json"
    foreign = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]},
               "model": "x"}
    settings.write_text(json.dumps(foreign), encoding="utf-8")
    desktop.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    monkeypatch.setattr(claude_setup, "claude_code_settings_path", lambda: settings)
    monkeypatch.setattr(claude_setup, "desktop_config_paths", lambda: [desktop])

    claude_setup.install()
    claude_setup.install()  # second run must not duplicate anything

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["model"] == "x"
    assert len(data["hooks"]["Stop"]) == 2                      # foreign + ours, once
    assert all(len(data["hooks"][e]) >= 1 for e in claude_setup.HOOK_EVENTS)
    cfg = json.loads(desktop.read_text(encoding="utf-8"))
    assert set(cfg["mcpServers"]) == {"other", "yoyo-dev"}
    assert (tmp_path / "settings.json.yoyo-backup").exists()

    claude_setup.uninstall()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["hooks"] == foreign["hooks"]                    # back to the original
    assert set(json.loads(desktop.read_text(encoding="utf-8"))["mcpServers"]) == {"other"}
