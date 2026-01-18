import os

import uvicorn

from app.core.logging import LOGGING_CONFIG

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

if __name__ == "__main__":
    uvicorn.run(
        "app:create_app",
        factory=True,
        host="0.0.0.0",
        port=5000,
        reload=DEBUG,
        workers=1 if DEBUG else int(os.getenv("WORKERS", "2")),
        timeout_keep_alive=120,
        access_log=True,
        log_config=LOGGING_CONFIG,
    )
