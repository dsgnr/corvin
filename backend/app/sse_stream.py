"""
Reusable SSE stream generator with pure pub/sub updates.

Streams wait for notifications on a channel and fetch fresh data when notified.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

from fastapi import Request
from sse_starlette.sse import EventSourceResponse

from app.extensions import sse_executor
from app.sse_hub import hub


def wants_sse(request: Request) -> bool:
    """Check if the client wants an SSE stream."""
    return "text/event-stream" in request.headers.get("accept", "")


def sse_cors_headers(request: Request) -> dict:
    """
    Generate CORS headers for SSE responses.

    Args:
        request: The incoming FastAPI request.

    Returns:
        Dictionary of CORS headers.
    """
    origin = request.headers.get("origin", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }


async def create_sse_stream(
    channel: str,
    fetch_data: Callable[[], Any],
    heartbeat_interval: int = 30,
):
    """
    Create a pure pub/sub SSE stream generator.

    Sends initial data immediately, then waits for notifications to send updates.

    Args:
        channel: SSE hub channel to subscribe to.
        fetch_data: Function returning data to send (called in executor).
        heartbeat_interval: Seconds between heartbeat comments.

    Yields:
        SSE event dicts with 'data' or 'comment' keys.
    """
    event_loop = asyncio.get_running_loop()

    # Send initial data immediately
    data = await event_loop.run_in_executor(sse_executor, fetch_data)
    yield {"data": json.dumps(data, default=str)}

    async with hub.subscribe(channel) as notification_queue:
        while True:
            try:
                await asyncio.wait_for(
                    notification_queue.get(), timeout=heartbeat_interval
                )

                # Received notification - fetch and send fresh data
                data = await event_loop.run_in_executor(sse_executor, fetch_data)
                yield {"data": json.dumps(data, default=str)}

            except TimeoutError:
                # No notification within heartbeat interval - send heartbeat
                yield {"comment": "heartbeat"}


def sse_response(
    request: Request,
    channel: str,
    fetch_data: Callable[[], Any],
    **kwargs,
) -> EventSourceResponse:
    """
    Create an SSE response with proper headers.

    Args:
        request: FastAPI request object (used for CORS origin).
        channel: SSE hub channel to subscribe to.
        fetch_data: Function returning data to send.
        **kwargs: Additional arguments passed to create_sse_stream.

    Returns:
        EventSourceResponse configured for SSE streaming.
    """
    return EventSourceResponse(
        create_sse_stream(channel, fetch_data, **kwargs),
        headers=sse_cors_headers(request),
    )
