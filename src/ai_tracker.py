import os
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

def main():
    print("AI/IDE Tracker Started!")
    base_url = get_yoyo_url()
    print(f"Sending updates to: {base_url}/api/tracker")
    
    last_state = None
    
    while True:
        title = get_active_window_title().lower()
        state = "IDLE"
        
        if "claude" in title or "chatgpt" in title or "gemini" in title:
            state = "AI_WEB"
        elif "code" in title or "cursor" in title or "pycharm" in title or "intellij" in title:
            state = "IDE"
            
        if state != last_state:
            # Send update to backend
            data = json.dumps({"state": state}).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/api/tracker", 
                data=data, 
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    pass
                print(f"State changed -> {state}")
                last_state = state
            except URLError as e:
                print(f"Failed to send update: {e}")
                
        time.sleep(2)

if __name__ == "__main__":
    main()
