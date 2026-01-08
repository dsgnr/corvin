"""SSE endpoint for download progress."""

import json
import time

from flask import Blueprint, Response

from app.services import progress_service

bp = Blueprint("progress", __name__, url_prefix="/api/progress")


@bp.get("/<int:video_id>/stream")
def stream(video_id: int):
    def generate():
        last = None
        idle = 0
        while True:
            data = progress_service.get(video_id)
            if data and data != last:
                yield f"data: {json.dumps(data)}\n\n"
                last = data
                idle = 0
                if data.get("status") in ("completed", "error"):
                    break
            else:
                idle += 1
            if idle > 120:  # 60s timeout
                yield f"data: {json.dumps({'video_id': video_id, 'status': 'timeout'})}\n\n"
                break
            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
