"""Tests for SSE hub pub/sub functionality."""

import asyncio
from unittest.mock import patch

import pytest

from app.sse_hub import Channel, SSEHub, broadcast, hub


class TestChannel:
    """Tests for Channel enum and helper methods."""

    def test_channel_values(self):
        """Should have expected channel values."""
        assert Channel.LISTS == "lists"
        assert Channel.TASKS == "tasks"
        assert Channel.TASKS_STATS == "tasks:stats"
        assert Channel.PROGRESS == "progress"
        assert Channel.HISTORY == "history"

    def test_list_videos_channel(self):
        """Should generate correct list videos channel name."""
        assert Channel.list_videos(123) == "list:123:videos"

    def test_list_tasks_channel(self):
        """Should generate correct list tasks channel name."""
        assert Channel.list_tasks(456) == "list:456:tasks"

    def test_list_history_channel(self):
        """Should generate correct list history channel name."""
        assert Channel.list_history(789) == "list:789:history"


class TestSSEHub:
    """Tests for SSEHub class."""

    @pytest.mark.asyncio
    async def test_subscribe_creates_queue(self):
        """Should create a queue when subscribing."""
        test_hub = SSEHub()

        async with test_hub.subscribe("test_channel") as queue:
            assert isinstance(queue, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_subscribe_captures_event_loop(self):
        """Should capture event loop on first subscription."""
        test_hub = SSEHub()
        assert test_hub._loop is None

        async with test_hub.subscribe("test_channel"):
            assert test_hub._loop is not None

    @pytest.mark.asyncio
    async def test_subscribe_cleanup(self):
        """Should clean up subscriber on context exit."""
        test_hub = SSEHub()

        async with test_hub.subscribe("test_channel"):
            assert "test_channel" in test_hub._subscribers
            assert len(test_hub._subscribers["test_channel"]) == 1

        # After context exit, channel should be removed (no subscribers)
        assert "test_channel" not in test_hub._subscribers

    @pytest.mark.asyncio
    async def test_broadcast_dispatches_to_subscribers(self):
        """Should dispatch notification to all subscribers."""
        test_hub = SSEHub()

        async with test_hub.subscribe("test_channel") as queue:
            # Broadcast to the channel
            test_hub.broadcast("test_channel")

            # Give the event loop a chance to process
            await asyncio.sleep(0.01)

            # Queue should have received the notification
            assert not queue.empty()
            msg = queue.get_nowait()
            assert msg is True

    @pytest.mark.asyncio
    async def test_broadcast_multiple_channels(self):
        """Should broadcast to multiple channels at once."""
        test_hub = SSEHub()

        async with test_hub.subscribe("channel1") as q1:
            async with test_hub.subscribe("channel2") as q2:
                test_hub.broadcast("channel1", "channel2")

                await asyncio.sleep(0.01)

                assert not q1.empty()
                assert not q2.empty()

    @pytest.mark.asyncio
    async def test_broadcast_ignores_unsubscribed_channels(self):
        """Should not fail when broadcasting to channels with no subscribers."""
        test_hub = SSEHub()

        # Set up the loop first
        async with test_hub.subscribe("other_channel"):
            # This should not raise
            test_hub.broadcast("nonexistent_channel")

    def test_broadcast_without_loop_does_nothing(self):
        """Should do nothing if no event loop is set."""
        test_hub = SSEHub()
        assert test_hub._loop is None

        # Should not raise
        test_hub.broadcast("test_channel")

    @pytest.mark.asyncio
    async def test_dispatch_handles_full_queue(self):
        """Should drop notifications when queue is full."""
        test_hub = SSEHub()

        async with test_hub.subscribe("test_channel") as queue:
            # Fill the queue (maxsize=100)
            for _ in range(100):
                queue.put_nowait(True)

            # This should not raise even though queue is full
            test_hub._dispatch("test_channel")


class TestGlobalHub:
    """Tests for global hub instance and broadcast function."""

    def test_global_hub_exists(self):
        """Should have a global hub instance."""
        assert hub is not None
        assert isinstance(hub, SSEHub)

    @pytest.mark.asyncio
    async def test_broadcast_function(self):
        """Should call hub.broadcast with channels."""
        with patch.object(hub, "broadcast") as mock_broadcast:
            broadcast(Channel.TASKS, Channel.LISTS)
            mock_broadcast.assert_called_once_with(Channel.TASKS, Channel.LISTS)
