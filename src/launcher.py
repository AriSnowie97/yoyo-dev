import sys
import threading
import time
import socket
from contextlib import closing
import uvicorn
import webview

# We must import the app so PyInstaller knows to bundle it
from main import app
import ai_tracker

def is_port_in_use(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_server():
    # We disable reload because it can cause issues in frozen executables
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)

def main():
    # Start the AI Tracker thread
    threading.Thread(target=ai_tracker.main, daemon=True).start()
    
    # Start the uvicorn server in a background thread
    threading.Thread(target=start_server, daemon=True).start()
    
    # Wait until the port is open before launching the webview
    for _ in range(30):
        if is_port_in_use(8000):
            time.sleep(0.5)
            break
        time.sleep(0.5)
        
    webview.create_window('YoYo Dev', 'http://127.0.0.1:8000', width=1200, height=800)
    webview.start()

if __name__ == "__main__":
    main()
