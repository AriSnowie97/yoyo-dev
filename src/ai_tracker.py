import os
import re
import time
import ctypes
import json
import urllib.request
from urllib.error import URLError

def get_yoyo_url():
    url = os.environ.get("YOYO_URL")
    if not url:
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("YOYO_URL="):
                        url = line.split("=", 1)[1]
                        break
        except Exception:
            pass
    return url or "http://localhost:8000"

def get_active_window_title():
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value
    except Exception:
        return ""

def classify_window(title: str):
    """
    Returns (state, detail) where:
      state  — "AI_WEB" | "IDE" | "IDLE"
      detail — short human-readable description of what is open
    """
    tl = title.lower()

    # ── Antigravity IDE ────────────────────────────────────
    if "antigravity" in tl:
        detail = _extract_page_name(title, "Antigravity")
        return "AI_WEB", f"Antigravity: {detail}" if detail else "Antigravity IDE"

    # ── AI / Claude / ChatGPT / Gemini ────────────────────
    if "claude" in tl:
        detail = _extract_page_name(title, "Claude")
        return "AI_WEB", detail

    if "chatgpt" in tl:
        detail = _extract_page_name(title, "ChatGPT")
        return "AI_WEB", detail

    if "gemini" in tl:
        detail = _extract_page_name(title, "Gemini")
        return "AI_WEB", detail

    if "copilot" in tl and ("chat" in tl or "github" in tl):
        return "AI_WEB", "GitHub Copilot Chat"

    if "perplexity" in tl:
        return "AI_WEB", "Perplexity AI"

    # ── IDE / Code editors ─────────────────────────────────
    if "visual studio code" in tl or " — vs code" in tl or "- visual studio code" in tl:
        detail = _extract_vscode_file(title)
        return "IDE", detail

    if "cursor" in tl:
        detail = _extract_vscode_file(title)
        return "IDE", f"Cursor: {detail}" if detail else "Cursor"

    if "pycharm" in tl:
        detail = _extract_ide_project(title)
        return "IDE", f"PyCharm: {detail}" if detail else "PyCharm"

    if "intellij" in tl:
        detail = _extract_ide_project(title)
        return "IDE", f"IntelliJ: {detail}" if detail else "IntelliJ"

    if "sublime text" in tl:
        return "IDE", _extract_page_name(title, "Sublime Text")

    if "neovim" in tl or "nvim" in tl or " vim" in tl:
        return "IDE", _extract_page_name(title, "Vim")

    return "IDLE", ""


def _extract_page_name(title: str, app_name: str) -> str:
    """
    Strip the app name suffix / browser suffix and return the page/tab name.
    Handles Chrome, Firefox ("— Mozilla Firefox"), Edge, etc.
    """
    # Remove common browser suffixes first
    browser_suffixes = [
        r"\s*[\-–—]\s*Mozilla Firefox",
        r"\s*[\-–—]\s*Google Chrome",
        r"\s*[\-–—]\s*Microsoft Edge",
        r"\s*[\-–—]\s*Opera",
        r"\s*[\-–—]\s*Brave",
    ]
    cleaned = title
    for pattern in browser_suffixes:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # Common patterns:  "Page title - Claude"  or  "Claude - Page title"
    parts = re.split(r"\s*[-–—]\s*", cleaned)
    parts = [p.strip() for p in parts if p.strip() and app_name.lower() not in p.lower()]
    if parts:
        return parts[0][:60]   # cap length
    return app_name


def _extract_vscode_file(title: str) -> str:
    """Return the file name VS Code is showing, e.g. 'app.js — yoyo-dev'."""
    # VS Code title format:  "filename.ext - folder - Visual Studio Code"
    parts = re.split(r"\s*[-–—]\s*", title)
    useful = [p.strip() for p in parts if p.strip()
              and "visual studio code" not in p.lower()
              and "vs code" not in p.lower()]
    return " · ".join(useful[:2]) if useful else "VS Code"


def _extract_ide_project(title: str) -> str:
    parts = re.split(r"\s*[-–—]\s*", title)
    useful = [p.strip() for p in parts
              if p.strip()
              and "pycharm" not in p.lower()
              and "intellij" not in p.lower()]
    return useful[0][:50] if useful else ""


def main():
    print("AI/IDE Tracker Started!")
    base_url = get_yoyo_url()
    print(f"Sending updates to: {base_url}/api/tracker")

    last_state  = None
    last_detail = None

    while True:
        title = get_active_window_title()
        state, detail = classify_window(title)

        # Send update when state OR detail changes
        if state != last_state or detail != last_detail:
            data = json.dumps({
                "state":        state,
                "detail":       detail,
                "window_title": title[:120],   # full raw title (capped)
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{base_url}/api/tracker",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5):
                    pass
                print(f"State → {state}  |  {detail or title[:60]}")
                last_state  = state
                last_detail = detail
            except URLError as e:
                print(f"Failed to send update: {e}")

        time.sleep(2)


if __name__ == "__main__":
    main()
