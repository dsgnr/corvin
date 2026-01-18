"""Tests for SSE stream utilities."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSseCorsHeaders:
    """Tests for sse_cors_headers function."""

    def test_cors_headers_with_origin(self):
        """Should use request origin in CORS headers."""
        from app.sse_stream import sse_cors_headers

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "http://localhost:3000"

        headers = sse_cors_headers(mock_request)

        assert headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert headers["Access-Control-Allow-Credentials"] == "true"
        assert headers["Cache-Control"] == "no-cache"
        assert headers["Connection"] == "keep-alive"

    def test_cors_headers_without_origin(self):
        """Should default to * when no origin header."""
        from app.sse_stream import sse_cors_headers

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "*"

        headers = sse_cors_headers(mock_request)

        assert headers["Access-Control-Allow-Origin"] == "*"


class TestCreateSseStream:
    """Tests for create_sse_stream async generator."""

    @pytest.mark.asyncio
    async def test_sends_initial_data_immediately(self):
        """Should send data immediately on connection."""
        from app.sse_stream import create_sse_stream

        fetch_data = MagicMock(return_value={"test": "data"})

        mock_queue = AsyncMock()
        mock_queue.get = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("app.sse_stream.hub") as mock_hub:
            mock_hub.subscribe.return_value.__aenter__ = AsyncMock(
                return_value=mock_queue
            )
            mock_hub.subscribe.return_value.__aexit__ = AsyncMock()

            with patch("app.sse_stream.sse_executor"):
                with patch("asyncio.get_running_loop") as mock_loop:

                    async def run_in_executor_side_effect(executor, func, *args):
                        return func(*args) if args else func()

                    mock_loop.return_value.run_in_executor = AsyncMock(
                        side_effect=run_in_executor_side_effect
                    )

                    stream = create_sse_stream("test_channel", fetch_data)

                    # Get first message - should be immediate data
                    first_message = await stream.__anext__()

                    assert "data" in first_message
                    assert '"test": "data"' in first_message["data"]

    @pytest.mark.asyncio
    async def test_sends_data_on_notification(self):
        """Should fetch and send data when notification received."""
        from app.sse_stream import create_sse_stream

        fetch_data = MagicMock(return_value={"updated": True})

        call_count = 0

        async def mock_get():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                # First call returns notification
                return True
            raise TimeoutError

        mock_queue = AsyncMock()
        mock_queue.get = mock_get

        with patch("app.sse_stream.hub") as mock_hub:
            mock_hub.subscribe.return_value.__aenter__ = AsyncMock(
                return_value=mock_queue
            )
            mock_hub.subscribe.return_value.__aexit__ = AsyncMock()

            with patch("app.sse_stream.sse_executor"):
                with patch("asyncio.get_running_loop") as mock_loop:

                    async def run_in_executor_side_effect(executor, func, *args):
                        return func(*args) if args else func()

                    mock_loop.return_value.run_in_executor = AsyncMock(
                        side_effect=run_in_executor_side_effect
                    )

                    stream = create_sse_stream("test_channel", fetch_data)

                    # First message (initial data)
                    await stream.__anext__()

                    # Second message (notification triggered)
                    second_message = await stream.__anext__()

                    assert "data" in second_message

    @pytest.mark.asyncio
    async def test_sends_heartbeat_on_timeout(self):
        """Should send heartbeat comment when no notifications."""
        from app.sse_stream import create_sse_stream

        fetch_data = MagicMock(return_value={"test": "data"})

        mock_queue = AsyncMock()
        mock_queue.get = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("app.sse_stream.hub") as mock_hub:
            mock_hub.subscribe.return_value.__aenter__ = AsyncMock(
                return_value=mock_queue
            )
            mock_hub.subscribe.return_value.__aexit__ = AsyncMock()

            with patch("app.sse_stream.sse_executor"):
                with patch("asyncio.get_running_loop") as mock_loop:

                    async def run_in_executor_side_effect(executor, func, *args):
                        return func(*args) if args else func()

                    mock_loop.return_value.run_in_executor = AsyncMock(
                        side_effect=run_in_executor_side_effect
                    )

                    # Use short heartbeat interval for test
                    stream = create_sse_stream(
                        "test_channel", fetch_data, heartbeat_interval=1
                    )

                    # First message (initial data)
                    first = await stream.__anext__()
                    assert "data" in first

                    # Second message should be heartbeat after timeout
                    second = await stream.__anext__()
                    assert "comment" in second
                    assert second["comment"] == "heartbeat"


class TestSseResponse:
    """Tests for sse_response convenience function."""

    def test_returns_event_source_response(self):
        """Should return EventSourceResponse with correct headers."""
        from app.sse_stream import sse_response

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "http://localhost:3000"

        response = sse_response(
            mock_request,
            "test_channel",
            lambda: {"test": "data"},
        )

        # Check it's an EventSourceResponse
        from sse_starlette.sse import EventSourceResponse

        assert isinstance(response, EventSourceResponse)
