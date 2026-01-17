import os

import uvicorn

from app.core.logging import LOGGING_CONFIG

# Production mode when not running with reload
DEV_MODE = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")

if __name__ == "__main__":
    uvicorn.run(
        "app:create_app",
        factory=True,
        host="0.0.0.0",
        port=5000,
        reload=DEV_MODE,
        workers=1 if DEV_MODE else int(os.getenv("WORKERS", "1")),
        timeout_keep_alive=120,
        access_log=True,
        log_config=LOGGING_CONFIG,
    )
