"""Entry point: ``uvicorn src.main:app`` (Railway) or imported by launcher.py.

All logic lives in the ``yoyo`` package; see docs/ARCHITECTURE.md.
"""

import os
import sys

# Make the ``yoyo`` package importable however the app is started.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yoyo.api.app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
