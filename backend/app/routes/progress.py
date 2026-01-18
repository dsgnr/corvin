"""
SSE endpoint for download progress updates.

Streams real-time progress data for active downloads.
"""

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.services import progress_service
from app.sse_hub import Channel, hub
from app.sse_stream import sse_cors_headers, wants_sse

router = APIRouter(prefix="/api/progress", tags=["Progress"])


@router.get("")
async def get_progress(request: Request):
    """
    Get download progress for all active downloads.

    Supports two modes:
    - Regular JSON response for standard requests
    - Server-Sent Events (SSE) stream for real-time updates when Accept header
      includes 'text/event-stream'

    The SSE stream uses push notifications from the progress service,
    with deduplication to avoid sending unchanged data.
    """
    if not wants_sse(request):
        return progress_service.get_all()

    async def generate_progress_stream():
        """
        SSE stream for download progress updates.

        Streams progress data whenever it changes. Uses JSON comparison
        for deduplication. Terminates after ~5 minutes of inactivity
        to free up connections.
        """
        previous_json: str | None = None
        idle_counter = 0
        max_idle_iterations = 600  # ~5 minutes at 0.5s intervals
        queue_timeout_seconds = 0  # First iteration: instant response

        async with hub.subscribe(Channel.PROGRESS) as notification_queue:
            while True:
                try:
                    await asyncio.wait_for(
                        notification_queue.get(), timeout=queue_timeout_seconds
                    )
                except TimeoutError:
                    pass
                finally:
                    queue_timeout_seconds = 0.5  # Subsequent iterations: 0.5s polling

                # Fetch current progress data
                progress_data = progress_service.get_all()
                current_json = json.dumps(progress_data, sort_keys=True)

                # Only send if data has changed
                if current_json != previous_json:
                    yield {"data": current_json}
                    previous_json = current_json
                    idle_counter = 0
                else:
                    idle_counter += 1

                # Terminate stream after extended inactivity
                if idle_counter > max_idle_iterations:
                    yield {"data": json.dumps({"status": "timeout"})}
                    break

    return EventSourceResponse(
        generate_progress_stream(), headers=sse_cors_headers(request)
    )
