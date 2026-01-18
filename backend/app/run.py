"""
Application entry point for development.

Run directly with `python -m app.run` or via uvicorn.
"""

import uvicorn

from app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.run:app", host="0.0.0.0", port=5000, reload=True)
