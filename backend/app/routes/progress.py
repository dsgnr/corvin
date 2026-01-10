"""SSE endpoint for download progress - streams all active downloads."""

import json
import time

from flask import Response
from flask_openapi3 import APIBlueprint, Tag

from app.services import progress_service

tag = Tag(name="Progress", description="Download progress streaming")
bp = APIBlueprint("progress", __name__, url_prefix="/api/progress", abp_tags=[tag])


@bp.get("/stream")
def stream():
    """Stream all active download progress via SSE."""

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
