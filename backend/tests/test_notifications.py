"""Tests for the notification system."""

from unittest.mock import MagicMock, patch

import requests

from app.schemas.notifications import ConfigField, Event, EventConfig
from app.services.notifications.discord import DiscordNotifier
from app.services.notifications.gotify import GotifyNotifier
from app.services.notifications.jellyfin import JellyfinNotifier
from app.services.notifications.notifier import BaseNotifier
from app.services.notifications.ntfy import NtfyNotifier
from app.services.notifications.plex import PlexNotifier
from app.services.notifications.registry import NotifierRegistry
from app.services.notifications.service import NotificationService
from app.services.notifications.slack import SlackNotifier


class TestConfigField:
    """Tests for ConfigField dataclass."""

    def test_to_dict_basic(self):
        field = ConfigField(type="string", label="Test Field")
        result = field.to_dict()
        assert result["type"] == "string"
        assert result["label"] == "Test Field"
        assert "dynamic_options" not in result
        assert "help" not in result

    def test_to_dict_with_options(self):
        field = ConfigField(
            type="select",
            label="Library",
            help="Select a library",
            dynamic_options="libraries",
        )
        result = field.to_dict()
        assert result["dynamic_options"] == "libraries"
        assert result["help"] == "Select a library"


class TestEventConfig:
    """Tests for EventConfig dataclass."""

    def test_to_dict(self):
        config = EventConfig(
            event=Event.DOWNLOAD_COMPLETED,
            label="Download Complete",
            description="Triggered when download finishes",
            default=True,
        )
        result = config.to_dict()
        assert result["id"] == "download_completed"
        assert result["label"] == "Download Complete"
        assert result["description"] == "Triggered when download finishes"
        assert result["default"] is True


class TestNotifierRegistry:
    """Tests for NotifierRegistry."""

    def test_get_registered_notifier(self):
        notifier_cls = NotifierRegistry.get("plex")
        assert notifier_cls is PlexNotifier

    def test_get_unknown_notifier(self):
        result = NotifierRegistry.get("nonexistent")
        assert result is None

    def test_all_returns_list(self):
        notifiers = NotifierRegistry.all()
        assert isinstance(notifiers, list)
        assert len(notifiers) >= 6  # plex, jellyfin, slack, discord, ntfy, gotify

    def test_all_contains_expected_fields(self):
        notifiers = NotifierRegistry.all()
        for notifier in notifiers:
            assert "id" in notifier
            assert "name" in notifier
            assert "config_schema" in notifier
            assert "supported_events" in notifier


class TestHTTPNotifier:
    """Tests for HTTPNotifier base class."""

    def test_handle_error_timeout(self):
        notifier = PlexNotifier({})
        success, msg = notifier._handle_error(requests.Timeout())
        assert success is False
        assert "timed out" in msg.lower()

    def test_handle_error_connection(self):
        notifier = PlexNotifier({})
        success, msg = notifier._handle_error(requests.ConnectionError())
        assert success is False
        assert "connect" in msg.lower()

    def test_handle_error_401(self):
        notifier = PlexNotifier({})
        response = MagicMock()
        response.status_code = 401
        error = requests.HTTPError(response=response)
        success, msg = notifier._handle_error(error)
        assert success is False
        assert "credentials" in msg.lower()

    def test_handle_error_404(self):
        notifier = PlexNotifier({})
        response = MagicMock()
        response.status_code = 404
        error = requests.HTTPError(response=response)
        success, msg = notifier._handle_error(error)
        assert success is False
        assert "not found" in msg.lower()


class TestPlexNotifier:
    """Tests for PlexNotifier."""

    def test_init(self):
        config = {
            "url": "http://localhost:32400",
            "token": "test-token",
            "library_id": "1",
        }
        notifier = PlexNotifier(config)
        assert notifier.url == "http://localhost:32400"
        assert notifier.token == "test-token"
        assert notifier.library_id == "1"

    def test_init_strips_trailing_slash(self):
        config = {"url": "http://localhost:32400/"}
        notifier = PlexNotifier(config)
        assert notifier.url == "http://localhost:32400"

    def test_test_connection_missing_url(self):
        notifier = PlexNotifier({})
        success, msg = notifier.test_connection()
        assert success is False
        assert "URL" in msg

    def test_test_connection_missing_token(self):
        notifier = PlexNotifier({"url": "http://localhost:32400"})
        success, msg = notifier.test_connection()
        assert success is False
        assert "token" in msg.lower()

    @patch.object(PlexNotifier, "_get")
    def test_test_connection_success(self, mock_get):
        mock_response = MagicMock()
        mock_get.return_value = mock_response

        notifier = PlexNotifier({"url": "http://localhost:32400", "token": "test"})
        success, msg = notifier.test_connection()
        assert success is True
        assert "Connected" in msg

    @patch.object(PlexNotifier, "_get")
    def test_get_libraries(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b"""
        <MediaContainer>
            <Directory key="1" title="Movies" type="movie"/>
            <Directory key="2" title="TV Shows" type="show"/>
        </MediaContainer>
        """
        mock_get.return_value = mock_response

        notifier = PlexNotifier({"url": "http://localhost:32400", "token": "test"})
        libraries = notifier.get_libraries()
        assert len(libraries) == 2
        assert libraries[0]["id"] == "1"
        assert libraries[0]["title"] == "Movies"

    @patch.object(PlexNotifier, "_get")
    def test_scan_library(self, mock_get):
        mock_response = MagicMock()
        mock_get.return_value = mock_response

        notifier = PlexNotifier(
            {"url": "http://localhost:32400", "token": "test", "library_id": "1"}
        )
        result = notifier._scan()
        assert result is True
        mock_get.assert_called()


class TestJellyfinNotifier:
    """Tests for JellyfinNotifier."""

    def test_init(self):
        config = {
            "url": "http://localhost:8096",
            "api_key": "test-key",
            "library_id": "abc123",
        }
        notifier = JellyfinNotifier(config)
        assert notifier.url == "http://localhost:8096"
        assert notifier.api_key == "test-key"
        assert notifier.library_id == "abc123"

    def test_headers_include_content_type(self):
        notifier = JellyfinNotifier({"api_key": "test"})
        headers = notifier._headers
        assert "Content-Type" in headers
        assert "application/json" in headers["Content-Type"]
        assert "Accept" in headers

    def test_test_connection_missing_url(self):
        notifier = JellyfinNotifier({})
        success, msg = notifier.test_connection()
        assert success is False
        assert "URL" in msg

    def test_test_connection_missing_api_key(self):
        notifier = JellyfinNotifier({"url": "http://localhost:8096"})
        success, msg = notifier.test_connection()
        assert success is False
        assert "api key" in msg.lower()

    @patch.object(JellyfinNotifier, "_get")
    def test_test_connection_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ServerName": "Test Jellyfin",
            "Version": "10.8.0",
        }
        mock_get.return_value = mock_response

        notifier = JellyfinNotifier({"url": "http://localhost:8096", "api_key": "test"})
        success, msg = notifier.test_connection()
        assert success is True
        assert "Test Jellyfin" in msg

    @patch.object(JellyfinNotifier, "_get")
    def test_get_libraries(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"ItemId": "abc", "Name": "Movies", "CollectionType": "movies"},
            {"Name": "Music", "CollectionType": "music"},
        ]
        mock_get.return_value = mock_response

        notifier = JellyfinNotifier({"url": "http://localhost:8096", "api_key": "test"})
        libraries = notifier.get_libraries()
        assert len(libraries) == 2
        assert libraries[0]["id"] == "abc"
        assert libraries[1]["id"] == "Music"


class TestSlackNotifier:
    """Tests for SlackNotifier."""

    def test_init(self):
        config = {
            "webhook_url": "https://hooks.slack.com/services/xxx",
            "channel": "#downloads",
            "username": "TestBot",
        }
        notifier = SlackNotifier(config)
        assert notifier.webhook_url == "https://hooks.slack.com/services/xxx"
        assert notifier.channel == "#downloads"
        assert notifier.username == "TestBot"

    def test_init_defaults(self):
        notifier = SlackNotifier({})
        assert notifier.username == "Corvin"
        assert notifier.channel == ""

    def test_test_connection_missing_webhook(self):
        notifier = SlackNotifier({})
        success, msg = notifier.test_connection()
        assert success is False
        assert "Webhook URL" in msg

    @patch.object(SlackNotifier, "_post")
    def test_test_connection_success(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = SlackNotifier({"webhook_url": "https://hooks.slack.com/xxx"})
        success, msg = notifier.test_connection()
        assert success is True
        assert "sent" in msg.lower()

    @patch.object(SlackNotifier, "_post")
    def test_on_download_completed(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = SlackNotifier({"webhook_url": "https://hooks.slack.com/xxx"})
        result = notifier.on_download_completed({"title": "Test Video"})
        assert result is True
        mock_post.assert_called_once()

    @patch.object(SlackNotifier, "_post")
    def test_on_video_discovered(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = SlackNotifier({"webhook_url": "https://hooks.slack.com/xxx"})
        result = notifier.on_video_discovered(
            {"title": "Test", "list_name": "Channel", "count": 1}
        )
        assert result is True

    @patch.object(SlackNotifier, "_post")
    def test_on_sync_completed(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = SlackNotifier({"webhook_url": "https://hooks.slack.com/xxx"})
        result = notifier.on_sync_completed({"list_name": "Channel", "new_videos": 5})
        assert result is True


class TestDiscordNotifier:
    """Tests for DiscordNotifier."""

    def test_init(self):
        config = {
            "webhook_url": "https://discord.com/api/webhooks/xxx",
            "username": "TestBot",
            "avatar_url": "https://example.com/avatar.png",
        }
        notifier = DiscordNotifier(config)
        assert notifier.webhook_url == "https://discord.com/api/webhooks/xxx"
        assert notifier.username == "TestBot"
        assert notifier.avatar_url == "https://example.com/avatar.png"

    def test_init_defaults(self):
        notifier = DiscordNotifier({})
        assert notifier.username == "Corvin"
        assert notifier.avatar_url == ""

    def test_test_connection_missing_webhook(self):
        notifier = DiscordNotifier({})
        success, msg = notifier.test_connection()
        assert success is False
        assert "Webhook URL" in msg

    @patch.object(DiscordNotifier, "_post")
    def test_test_connection_success(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = DiscordNotifier(
            {"webhook_url": "https://discord.com/api/webhooks/xxx"}
        )
        success, msg = notifier.test_connection()
        assert success is True
        assert "sent" in msg.lower()

    @patch.object(DiscordNotifier, "_post")
    def test_on_download_completed(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = DiscordNotifier(
            {"webhook_url": "https://discord.com/api/webhooks/xxx"}
        )
        result = notifier.on_download_completed(
            {"title": "Test Video", "list_name": "Channel"}
        )
        assert result is True

        call_args = mock_post.call_args
        payload = call_args.kwargs.get("json", {})
        assert "embeds" in payload
        assert payload["embeds"][0]["color"] == 0x00FF00

    @patch.object(DiscordNotifier, "_post")
    def test_on_video_discovered(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = DiscordNotifier(
            {"webhook_url": "https://discord.com/api/webhooks/xxx"}
        )
        result = notifier.on_video_discovered({"title": "Test", "list_name": "Channel"})
        assert result is True

    @patch.object(DiscordNotifier, "_post")
    def test_on_sync_completed(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = DiscordNotifier(
            {"webhook_url": "https://discord.com/api/webhooks/xxx"}
        )
        result = notifier.on_sync_completed({"list_name": "Channel", "new_videos": 5})
        assert result is True


class TestNtfyNotifier:
    """Tests for NtfyNotifier."""

    def test_init(self):
        config = {
            "server_url": "https://ntfy.example.com",
            "topic": "test-topic",
            "access_token": "tk_xxx",
            "priority": "high",
        }
        notifier = NtfyNotifier(config)
        assert notifier.server_url == "https://ntfy.example.com"
        assert notifier.topic == "test-topic"
        assert notifier.access_token == "tk_xxx"
        assert notifier.priority == "high"

    def test_init_defaults(self):
        notifier = NtfyNotifier({})
        assert notifier.server_url == "https://ntfy.sh"
        assert notifier.priority == "default"

    def test_test_connection_missing_topic(self):
        notifier = NtfyNotifier({})
        success, msg = notifier.test_connection()
        assert success is False
        assert "Topic" in msg

    @patch.object(NtfyNotifier, "_post")
    def test_test_connection_success(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = NtfyNotifier({"topic": "test-topic"})
        success, msg = notifier.test_connection()
        assert success is True
        assert "sent" in msg.lower()

    @patch.object(NtfyNotifier, "_post")
    def test_on_download_completed(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = NtfyNotifier({"topic": "test-topic"})
        result = notifier.on_download_completed(
            {"title": "Test Video", "list_name": "Channel"}
        )
        assert result is True

        call_args = mock_post.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers["Title"] == "Download Complete"

    @patch.object(NtfyNotifier, "_post")
    def test_on_video_discovered(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = NtfyNotifier({"topic": "test-topic"})
        result = notifier.on_video_discovered({"title": "Test", "list_name": "Channel"})
        assert result is True

    @patch.object(NtfyNotifier, "_post")
    def test_on_sync_completed(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = NtfyNotifier({"topic": "test-topic"})
        result = notifier.on_sync_completed({"list_name": "Channel"})
        assert result is True

    @patch.object(NtfyNotifier, "_post")
    def test_auth_header_included(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = NtfyNotifier({"topic": "test", "access_token": "tk_secret"})
        notifier.on_download_completed({"title": "Test", "list_name": "Channel"})

        call_args = mock_post.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers["Authorization"] == "Bearer tk_secret"


class TestGotifyNotifier:
    """Tests for GotifyNotifier."""

    def test_init(self):
        config = {
            "server_url": "https://gotify.example.com",
            "app_token": "A_xxx",
            "priority": "8",
        }
        notifier = GotifyNotifier(config)
        assert notifier.server_url == "https://gotify.example.com"
        assert notifier.app_token == "A_xxx"
        assert notifier.priority == 8

    def test_init_defaults(self):
        notifier = GotifyNotifier({})
        assert notifier.priority == 5

    def test_test_connection_missing_url(self):
        notifier = GotifyNotifier({})
        success, msg = notifier.test_connection()
        assert success is False
        assert "URL" in msg

    def test_test_connection_missing_token(self):
        notifier = GotifyNotifier({"server_url": "https://gotify.example.com"})
        success, msg = notifier.test_connection()
        assert success is False
        assert "token" in msg.lower()

    @patch.object(GotifyNotifier, "_post")
    def test_test_connection_success(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = GotifyNotifier(
            {"server_url": "https://gotify.example.com", "app_token": "A_xxx"}
        )
        success, msg = notifier.test_connection()
        assert success is True
        assert "sent" in msg.lower()

    @patch.object(GotifyNotifier, "_post")
    def test_on_download_completed(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = GotifyNotifier(
            {"server_url": "https://gotify.example.com", "app_token": "A_xxx"}
        )
        result = notifier.on_download_completed(
            {"title": "Test Video", "list_name": "Channel"}
        )
        assert result is True

        call_args = mock_post.call_args
        payload = call_args.kwargs.get("json", {})
        assert payload["title"] == "Download Complete"

    @patch.object(GotifyNotifier, "_post")
    def test_on_video_discovered(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = GotifyNotifier(
            {"server_url": "https://gotify.example.com", "app_token": "A_xxx"}
        )
        result = notifier.on_video_discovered({"title": "Test", "list_name": "Channel"})
        assert result is True

    @patch.object(GotifyNotifier, "_post")
    def test_on_sync_completed(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = GotifyNotifier(
            {"server_url": "https://gotify.example.com", "app_token": "A_xxx"}
        )
        result = notifier.on_sync_completed({"list_name": "Channel"})
        assert result is True

    @patch.object(GotifyNotifier, "_post")
    def test_gotify_key_header(self, mock_post):
        mock_response = MagicMock()
        mock_post.return_value = mock_response

        notifier = GotifyNotifier(
            {"server_url": "https://gotify.example.com", "app_token": "A_secret"}
        )
        notifier.on_download_completed({"title": "Test", "list_name": "Channel"})

        call_args = mock_post.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers["X-Gotify-Key"] == "A_secret"


class TestNotificationService:
    """Tests for NotificationService."""

    def test_download_completed_convenience_method(self):
        with patch.object(NotificationService, "send") as mock_send:
            NotificationService.download_completed("Test Video", "/path/to/video")
            mock_send.assert_called_once_with(
                Event.DOWNLOAD_COMPLETED,
                {"title": "Test Video", "path": "/path/to/video"},
            )

    def test_download_completed_with_list_name(self):
        with patch.object(NotificationService, "send") as mock_send:
            NotificationService.download_completed(
                "Test Video", "/path/to/video", list_name="My Channel"
            )
            mock_send.assert_called_once_with(
                Event.DOWNLOAD_COMPLETED,
                {
                    "title": "Test Video",
                    "path": "/path/to/video",
                    "list_name": "My Channel",
                },
            )

    def test_video_discovered_convenience_method(self):
        with patch.object(NotificationService, "send") as mock_send:
            NotificationService.video_discovered("Test Video", "Test Channel", 3)
            mock_send.assert_called_once_with(
                Event.VIDEO_DISCOVERED,
                {"title": "Test Video", "list_name": "Test Channel", "count": 3},
            )

    def test_sync_completed_convenience_method(self):
        with patch.object(NotificationService, "send") as mock_send:
            NotificationService.sync_completed("Test Channel", 5, 100)
            mock_send.assert_called_once_with(
                Event.SYNC_COMPLETED,
                {"list_name": "Test Channel", "new_videos": 5, "total": 100},
            )


class TestBaseNotifierSubclassing:
    """Tests for BaseNotifier registration and dispatch."""

    def test_notifiers_are_registered(self):
        assert NotifierRegistry.get("plex") is PlexNotifier
        assert NotifierRegistry.get("jellyfin") is JellyfinNotifier
        assert NotifierRegistry.get("slack") is SlackNotifier
        assert NotifierRegistry.get("discord") is DiscordNotifier
        assert NotifierRegistry.get("ntfy") is NtfyNotifier
        assert NotifierRegistry.get("gotify") is GotifyNotifier

    def test_notify_dispatches_to_handler(self):
        class HandlerTestNotifier(BaseNotifier):
            id = "handler_test"
            name = "Handler Test"
            config_schema = {}
            supported_events = []
            handler_called = False

            def test_connection(self):
                return True, "OK"

            def on_download_completed(self, data):
                HandlerTestNotifier.handler_called = True
                return True

        notifier = HandlerTestNotifier({})
        notifier.notify(Event.DOWNLOAD_COMPLETED, {"title": "Test"})
        assert HandlerTestNotifier.handler_called is True

    def test_notify_returns_true_for_missing_handler(self):
        class NoHandlerNotifier(BaseNotifier):
            id = "no_handler_test"
            name = "No Handler"
            config_schema = {}
            supported_events = []

            def test_connection(self):
                return True, "OK"

        notifier = NoHandlerNotifier({})
        result = notifier.notify(Event.DOWNLOAD_COMPLETED, {})
        assert result is True


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_plex_uses_env_var_token(self):
        with patch.dict("os.environ", {"NOTIFICATION_PLEX_TOKEN": "env-token"}):
            from app.routes.notifications import _get_config_with_env

            config = {"url": "http://localhost:32400", "token": "db-token"}
            schema = {"token": {"type": "password"}, "url": {"type": "string"}}

            result = _get_config_with_env(config, "plex", schema)

            assert result["token"] == "env-token"
            assert result["url"] == "http://localhost:32400"

    def test_env_var_takes_precedence_over_db(self):
        with patch.dict("os.environ", {"NOTIFICATION_PLEX_TOKEN": "env-token"}):
            from app.routes.notifications import _get_config_with_env

            config = {"token": "db-token"}
            schema = {"token": {"type": "password"}}

            result = _get_config_with_env(config, "plex", schema)

            assert result["token"] == "env-token"

    def test_db_value_used_when_no_env_var(self):
        with patch.dict("os.environ", {}, clear=True):
            from app.routes.notifications import _get_config_with_env

            config = {"token": "db-token"}
            schema = {"token": {"type": "password"}}

            result = _get_config_with_env(config, "plex", schema)

            assert result["token"] == "db-token"

    def test_is_field_from_env_returns_true(self):
        with patch.dict("os.environ", {"NOTIFICATION_PLEX_TOKEN": "env-token"}):
            from app.routes.notifications import _is_field_from_env

            assert _is_field_from_env("plex", "token") is True

    def test_is_field_from_env_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            from app.routes.notifications import _is_field_from_env

            assert _is_field_from_env("plex", "token") is False

    def test_env_var_name_generation(self):
        from app.routes.notifications import _get_env_var_name

        assert _get_env_var_name("plex", "token") == "NOTIFICATION_PLEX_TOKEN"
        assert (
            _get_env_var_name("jellyfin", "api_key") == "NOTIFICATION_JELLYFIN_API_KEY"
        )
        assert (
            _get_env_var_name("slack", "webhook_url")
            == "NOTIFICATION_SLACK_WEBHOOK_URL"
        )
        assert (
            _get_env_var_name("discord", "webhook_url")
            == "NOTIFICATION_DISCORD_WEBHOOK_URL"
        )
        assert (
            _get_env_var_name("ntfy", "access_token")
            == "NOTIFICATION_NTFY_ACCESS_TOKEN"
        )
        assert (
            _get_env_var_name("gotify", "app_token") == "NOTIFICATION_GOTIFY_APP_TOKEN"
        )

    def test_mask_sensitive_fields_shows_env_flag(self):
        with patch.dict("os.environ", {"NOTIFICATION_PLEX_TOKEN": "env-token"}):
            from app.routes.notifications import _mask_sensitive_fields

            config = {"token": "env-token", "url": "http://localhost"}
            schema = {"token": {"type": "password"}, "url": {"type": "string"}}

            result = _mask_sensitive_fields(config, schema, "plex")

            assert result["token"] == ""
            assert result["_token_set"] is True
            assert result["_token_env"] is True
            assert result["url"] == "http://localhost"
