import os
import re
import time
import ctypes
import ctypes.wintypes
import json
import urllib.request
from urllib.error import URLError


def get_yoyo_url():
    url = os.environ.get("YOYO_URL")
    if not url:
        try:
            # Look for .env in script dir or cwd
            for candidate in [
                os.path.join(os.path.dirname(__file__), "..", ".env"),
                ".env",
            ]:
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("YOYO_URL="):
                                url = line.split("=", 1)[1].strip()
                                break
                    if url:
                        break
                except FileNotFoundError:
                    continue
        except Exception:
            pass
    return url or "http://localhost:8000"


# ── Win32 helpers ──────────────────────────────────────────────────────────────

def get_foreground_hwnd():
    try:
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return None


def get_window_title(hwnd) -> str:
    try:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value
    except Exception:
        return ""


def get_process_name(hwnd) -> str:
    """Return the .exe name of the process owning the given window handle."""
    try:
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_proc = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
        )
        if not h_proc:
            return ""
        buf = ctypes.create_unicode_buffer(260)
        size = ctypes.wintypes.DWORD(260)
        ctypes.windll.kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size))
        ctypes.windll.kernel32.CloseHandle(h_proc)
        return os.path.basename(buf.value).lower()  # e.g. "claude.exe"
    except Exception:
        return ""


# ── Classification ──────────────────────────────────────────────────────────────

# Desktop AI apps detected by process name
DESKTOP_AI_APPS = {
    "claude.exe":       ("🤖", "Claude Desktop"),
    "gemini.exe":       ("✨", "Gemini App"),
    "chatgpt.exe":      ("💬", "ChatGPT Desktop"),
    "copilot.exe":      ("🤝", "GitHub Copilot"),
    "msedge.exe":       None,   # browser — fall through to title check
    "chrome.exe":       None,
    "firefox.exe":      None,
    "brave.exe":        None,
    "opera.exe":        None,
}


def classify_window(title: str, process: str):
    """
    Returns (state, detail, app_emoji) where:
      state      — "AI_WEB" | "IDE" | "IDLE"
      detail     — short human-readable description
      app_emoji  — emoji for the app
    """
    tl = title.lower()

    # ── 1. Desktop AI apps (by process name) ──────────────────
    if process == "claude.exe":
        # Claude Desktop — window title is the conversation name
        conv = _strip_app_suffix(title, "Claude")
        detail = f"Claude Desktop: {conv}" if conv else "Claude Desktop"
        return "AI_WEB", detail, "🤖"

    if process == "gemini.exe":
        conv = _strip_app_suffix(title, "Gemini")
        detail = f"Gemini App: {conv}" if conv else "Gemini App"
        return "AI_WEB", detail, "✨"

    if process == "chatgpt.exe":
        conv = _strip_app_suffix(title, "ChatGPT")
        detail = f"ChatGPT Desktop: {conv}" if conv else "ChatGPT Desktop"
        return "AI_WEB", detail, "💬"

    # ── 2. Antigravity IDE ─────────────────────────────────────
    if "antigravity" in tl:
        detail = _extract_page_name(title, "Antigravity")
        return "AI_WEB", f"Antigravity: {detail}" if detail else "Antigravity IDE", "🪐"

    # ── 3. Browser AI (Claude, ChatGPT, Gemini, etc.) ─────────
    if "claude" in tl:
        detail = _extract_page_name(title, "Claude")
        return "AI_WEB", f"Claude: {detail}" if detail else "Claude", "🤖"

    if "chatgpt" in tl:
        detail = _extract_page_name(title, "ChatGPT")
        return "AI_WEB", f"ChatGPT: {detail}" if detail else "ChatGPT", "💬"

    # Gemini + Google AI Studio + NotebookLM
    if "gemini" in tl:
        detail = _extract_page_name(title, "Gemini")
        label = "Gemini Notebook" if "notebook" in tl else ("AI Studio" if "studio" in tl else "Gemini")
        return "AI_WEB", f"{label}: {detail}" if detail else label, "✨"

    if "notebooklm" in tl or "notebook lm" in tl:
        detail = _extract_page_name(title, "NotebookLM")
        return "AI_WEB", f"NotebookLM: {detail}" if detail else "NotebookLM", "📓"

    if "aistudio.google" in tl or "ai studio" in tl:
        return "AI_WEB", "Google AI Studio", "🔬"

    if "copilot" in tl and ("chat" in tl or "github" in tl or "microsoft" in tl):
        return "AI_WEB", "GitHub Copilot Chat", "🤝"

    if "perplexity" in tl:
        detail = _extract_page_name(title, "Perplexity")
        return "AI_WEB", f"Perplexity: {detail}" if detail else "Perplexity AI", "🔍"

    if "mistral" in tl or "le chat" in tl:
        return "AI_WEB", "Mistral / Le Chat", "🌊"

    if "grok" in tl and "x.com" not in tl:
        return "AI_WEB", "Grok AI", "🚀"

    # ── 4. IDE / Code editors ──────────────────────────────────
    if "visual studio code" in tl or " — vs code" in tl or "- visual studio code" in tl:
        detail = _extract_vscode_file(title)
        return "IDE", detail, "💻"

    if process in ("code.exe", "code - insiders.exe"):
        return "IDE", _extract_vscode_file(title) or "VS Code", "💻"

    if "cursor" in tl or process == "cursor.exe":
        detail = _extract_vscode_file(title)
        return "IDE", f"Cursor: {detail}" if detail else "Cursor", "💻"

    if "pycharm" in tl or process == "pycharm64.exe":
        detail = _extract_ide_project(title)
        return "IDE", f"PyCharm: {detail}" if detail else "PyCharm", "🐍"

    if "intellij" in tl or process in ("idea64.exe", "idea.exe"):
        detail = _extract_ide_project(title)
        return "IDE", f"IntelliJ: {detail}" if detail else "IntelliJ", "☕"

    if "sublime text" in tl or process == "sublime_text.exe":
        return "IDE", _extract_page_name(title, "Sublime Text") or "Sublime Text", "📝"

    if "neovim" in tl or "nvim" in tl or process in ("nvim.exe", "vim.exe"):
        return "IDE", _extract_page_name(title, "Vim") or "Vim/Neovim", "📝"

    return "IDLE", "", ""


# ── String helpers ──────────────────────────────────────────────────────────────

def _strip_app_suffix(title: str, app_name: str) -> str:
    """For desktop apps: just strip the app name itself from title."""
    parts = re.split(r"\s*[-–—]\s*", title)
    parts = [p.strip() for p in parts if p.strip() and app_name.lower() not in p.lower()]
    return parts[0][:60] if parts else ""


def _extract_page_name(title: str, app_name: str) -> str:
    """
    Strip the app name + browser suffix, return the page/tab name.
    Handles Firefox ("— Mozilla Firefox"), Chrome, Edge, etc.
    """
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

    parts = re.split(r"\s*[-–—]\s*", cleaned)
    parts = [p.strip() for p in parts if p.strip() and app_name.lower() not in p.lower()]
    return parts[0][:60] if parts else ""


def _extract_vscode_file(title: str) -> str:
    """Return 'filename · folder' from VS Code window title."""
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


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print("AI/IDE Tracker Started!")
    base_url = get_yoyo_url()
    print(f"Sending updates to: {base_url}/api/tracker")

    last_state  = None
    last_detail = None

    while True:
        hwnd    = get_foreground_hwnd()
        title   = get_window_title(hwnd) if hwnd else ""
        process = get_process_name(hwnd) if hwnd else ""

        state, detail, emoji = classify_window(title, process)

        # Send update when state OR detail changes
        if state != last_state or detail != last_detail:
            payload = json.dumps({
                "state":        state,
                "detail":       detail,
                "emoji":        emoji,
                "window_title": title[:120],
                "process":      process,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{base_url}/api/tracker",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5):
                    pass
                label = detail or title[:60] or process
                print(f"[{state}] {emoji}  {label}")
                last_state  = state
                last_detail = detail
            except URLError as e:
                print(f"Failed to send update: {e}")

        time.sleep(2)


if __name__ == "__main__":
    main()
