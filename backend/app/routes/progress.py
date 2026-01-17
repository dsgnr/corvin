"""SSE endpoint for download progress - streams all active downloads."""

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.services import progress_service

router = APIRouter(prefix="/api/progress", tags=["Progress"])


@router.get("/")
async def get_progress(request: Request):
    """Get download progress.

    If Accept header is 'text/event-stream', streams updates via SSE.
    Otherwise returns JSON object of current progress.
    """
    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept:
        return progress_service.get_all()

    # SSE stream
    async def generate():
        last_json = None
        idle = 0

        while True:
            data = progress_service.get_all()
            current_json = json.dumps(data, sort_keys=True)

            if current_json != last_json:
                yield {"data": current_json}
                last_json = current_json
                idle = 0
            else:
                idle += 1

            if idle > 600:
                yield {"data": json.dumps({"status": "timeout"})}
                break

            await asyncio.sleep(0.5)

    return EventSourceResponse(generate())
