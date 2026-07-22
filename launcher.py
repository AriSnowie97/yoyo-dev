import sys
import threading
import time
import webbrowser
import socket
from contextlib import closing
import uvicorn

# We must import the app so PyInstaller knows to bundle it
from main import app

def is_port_in_use(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def open_browser():
    # Wait until the port is open before launching the browser
    for _ in range(30):
        if is_port_in_use(8000):
            time.sleep(0.5)
            webbrowser.open("http://127.0.0.1:8000")
            break
        time.sleep(0.5)

def main():
    # Start the browser thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run the uvicorn server
    # We disable reload because it can cause issues in frozen executables
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
