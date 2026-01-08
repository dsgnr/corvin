"""SSE endpoint for download progress - streams all active downloads."""

import json
import time

from flask import Blueprint, Response

from app.services import progress_service

bp = Blueprint("progress", __name__, url_prefix="/api/progress")


@bp.get("/stream")
def stream():
    """
    Stream all active download progress.
    Sends updates whenever any download's progress changes.
    """

    def generate():
        last_json = None
        idle = 0

        while True:
            data = progress_service.get_all()
            current_json = json.dumps(data, sort_keys=True)

            if current_json != last_json:
                yield f"data: {current_json}\n\n"
                last_json = current_json
                idle = 0
            else:
                idle += 1

            # Keep alive for 5 minutes of inactivity
            if idle > 600:
                yield f"data: {json.dumps({'status': 'timeout'})}\n\n"
                break

            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
