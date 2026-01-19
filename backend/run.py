import os

import uvicorn

from app.core.logging import LOGGING_CONFIG

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# NOTE: WORKERS should be set to 1 for this application.
# Each uvicorn worker process spawns its own independent TaskWorker with its own
# thread pools for sync/download tasks. Multiple uvicorn workers means multiple
# TaskWorkers polling the same database without coordination, leading to:
# - Effective worker count = WORKERS × MAX_SYNC_WORKERS (e.g., 2 × 2 = 4 syncs)
# - Potential race conditions when grabbing pending tasks
# - No shared state between processes

if __name__ == "__main__":
    uvicorn.run(
        "app:create_app",
        factory=True,
        host="0.0.0.0",
        port=5000,
        reload=DEBUG,
        workers=1,
        timeout_keep_alive=120,
        access_log=True,
        log_config=LOGGING_CONFIG,
    )
