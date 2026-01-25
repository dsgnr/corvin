"""Tests for video list API endpoints."""

from unittest.mock import patch


class TestCreateList:
    """Tests for POST /api/lists."""

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_success(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should create a list with valid data."""
        mock_metadata.return_value = {}

        response = client.post(
            "/api/lists",
            json={
                "name": "My Channel",
                "url": "https://youtube.com/c/mychannel",
                "profile_id": sample_profile,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Channel"
        assert data["enabled"] is True
        mock_enqueue.assert_called_once()

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_with_metadata(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should populate metadata from yt-dlp."""
        mock_metadata.return_value = {
            "description": "Channel description",
            "thumbnail": "https://example.com/thumb.jpg",
        }

        response = client.post(
            "/api/lists",
            json={
                "name": "Channel With Metadata",
                "url": "https://youtube.com/c/withmetadata",
                "profile_id": sample_profile,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "Channel description"

    def test_create_list_missing_required_fields(self, client):
        """Should reject list without required fields."""
        response = client.post("/api/lists", json={"name": "Test"})
        assert response.status_code == 400

    def test_create_list_invalid_profile(self, client):
        """Should reject list with non-existent profile."""
        response = client.post(
            "/api/lists",
            json={
                "name": "Test",
                "url": "https://youtube.com/c/test",
                "profile_id": 9999,
            },
        )
        assert response.status_code == 404

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_duplicate_url(
        self, mock_enqueue, mock_metadata, client, sample_profile, sample_list
    ):
        """Should reject duplicate URL."""
        mock_metadata.return_value = {}
        response = client.post(
            "/api/lists",
            json={
                "name": "Duplicate",
                "url": "https://youtube.com/c/testchannel",
                "profile_id": sample_profile,
            },
        )
        assert response.status_code == 409

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_with_from_date(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should accept valid from_date."""
        mock_metadata.return_value = {}
        response = client.post(
            "/api/lists",
            json={
                "name": "Dated List",
                "url": "https://youtube.com/c/dated",
                "profile_id": sample_profile,
                "from_date": "20240101",
            },
        )
        assert response.status_code == 201
        assert response.json()["from_date"] == "20240101"

    def test_create_list_invalid_from_date(self, client, sample_profile):
        """Should reject invalid from_date format."""
        response = client.post(
            "/api/lists",
            json={
                "name": "Bad Date",
                "url": "https://youtube.com/c/baddate",
                "profile_id": sample_profile,
                "from_date": "invalid",
            },
        )
        assert response.status_code == 400


class TestCreateListNameFallback:
    """Tests for list name fallback logic when name is None."""

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_name_from_metadata_when_none(
        self, mock_enqueue, mock_metadata, client, sample_profile, db_session
    ):
        """Should use metadata name when name is not provided."""
        from app.routes.lists import _create_video_list

        mock_metadata.return_value = {"name": "Channel From Metadata"}

        video_list = _create_video_list(
            db=db_session,
            url="https://youtube.com/@metadatachannel",
            name=None,
            list_type="channel",
            profile_id=sample_profile,
        )

        assert video_list.name == "Channel From Metadata"
        assert video_list.source_name == "Channel From Metadata"

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_name_fallback_to_url(
        self, mock_enqueue, mock_metadata, client, sample_profile, db_session
    ):
        """Should use URL as name when both name and metadata name are None."""
        from app.routes.lists import _create_video_list

        mock_metadata.return_value = {}

        video_list = _create_video_list(
            db=db_session,
            url="https://youtube.com/@fallbackchannel",
            name=None,
            list_type="channel",
            profile_id=sample_profile,
        )

        assert video_list.name == "https://youtube.com/@fallbackchannel"
        assert video_list.source_name is None

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_explicit_name_takes_precedence(
        self, mock_enqueue, mock_metadata, client, sample_profile, db_session
    ):
        """Should use explicit name over metadata name."""
        from app.routes.lists import _create_video_list

        mock_metadata.return_value = {"name": "Metadata Name"}

        video_list = _create_video_list(
            db=db_session,
            url="https://youtube.com/@explicitchannel",
            name="Explicit Name",
            list_type="channel",
            profile_id=sample_profile,
        )

        assert video_list.name == "Explicit Name"
        assert video_list.source_name == "Metadata Name"


class TestCreateListsBulk:
    """Tests for POST /api/lists/bulk."""

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_bulk_create_success(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should accept bulk create request (async)."""
        mock_metadata.return_value = {"name": "Auto Name"}

        response = client.post(
            "/api/lists/bulk",
            json={
                "urls": [
                    "https://youtube.com/c/channel1",
                    "https://youtube.com/c/channel2",
                ],
                "profile_id": sample_profile,
                "list_type": "channel",
                "sync_frequency": "daily",
                "enabled": True,
                "auto_download": True,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert "message" in data
        assert data["count"] == 2

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_bulk_create_with_metadata_name(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should accept bulk create request."""
        mock_metadata.return_value = {"name": "Channel From Metadata"}

        response = client.post(
            "/api/lists/bulk",
            json={
                "urls": ["https://youtube.com/c/channel1"],
                "profile_id": sample_profile,
                "list_type": "channel",
                "sync_frequency": "daily",
                "enabled": True,
                "auto_download": True,
            },
        )

        assert response.status_code == 202
        assert response.json()["count"] == 1

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_bulk_create_fallback_name_from_url(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should accept bulk create request."""
        mock_metadata.return_value = {}

        response = client.post(
            "/api/lists/bulk",
            json={
                "urls": ["https://youtube.com/c/mychannel"],
                "profile_id": sample_profile,
                "list_type": "channel",
                "sync_frequency": "daily",
                "enabled": True,
                "auto_download": True,
            },
        )

        assert response.status_code == 202
        assert response.json()["count"] == 1

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_bulk_create_skips_duplicates(
        self, mock_enqueue, mock_metadata, client, sample_profile, sample_list
    ):
        """Should accept bulk create request (duplicates handled in background)."""
        mock_metadata.return_value = {"name": "New Channel"}

        response = client.post(
            "/api/lists/bulk",
            json={
                "urls": [
                    "https://youtube.com/c/testchannel",  # Duplicate from sample_list
                    "https://youtube.com/c/newchannel",
                ],
                "profile_id": sample_profile,
                "list_type": "channel",
                "sync_frequency": "daily",
                "enabled": True,
                "auto_download": True,
            },
        )

        assert response.status_code == 202
        assert response.json()["count"] == 2  # Count is URLs submitted, not created

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_bulk_create_skips_empty_urls(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should accept bulk create request."""
        mock_metadata.return_value = {"name": "Valid Channel"}

        response = client.post(
            "/api/lists/bulk",
            json={
                "urls": [
                    "",
                    "   ",
                    "https://youtube.com/c/valid",
                ],
                "profile_id": sample_profile,
                "list_type": "channel",
                "sync_frequency": "daily",
                "enabled": True,
                "auto_download": True,
            },
        )

        assert response.status_code == 202
        assert response.json()["count"] == 3  # Count is URLs submitted

    def test_bulk_create_invalid_profile(self, client):
        """Should reject bulk create with non-existent profile."""
        response = client.post(
            "/api/lists/bulk",
            json={
                "urls": ["https://youtube.com/c/channel1"],
                "profile_id": 9999,
                "list_type": "channel",
                "sync_frequency": "daily",
                "enabled": True,
                "auto_download": True,
            },
        )
        assert response.status_code == 404

    def test_bulk_create_empty_urls(self, client, sample_profile):
        """Should reject empty URLs list."""
        response = client.post(
            "/api/lists/bulk",
            json={
                "urls": [],
                "profile_id": sample_profile,
                "list_type": "channel",
                "sync_frequency": "daily",
                "enabled": True,
                "auto_download": True,
            },
        )
        assert response.status_code == 400

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_bulk_create_playlist_type(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should accept bulk create for playlists."""
        mock_metadata.return_value = {"name": "My Playlist"}

        response = client.post(
            "/api/lists/bulk",
            json={
                "urls": ["https://youtube.com/playlist?list=PLxxx"],
                "profile_id": sample_profile,
                "list_type": "playlist",
                "sync_frequency": "weekly",
                "enabled": True,
                "auto_download": False,
            },
        )

        assert response.status_code == 202
        assert response.json()["count"] == 1


class TestListAll:
    """Tests for GET /api/lists."""

    def test_list_all_empty(self, client):
        """Should return empty list when no lists exist."""
        response = client.get("/api/lists")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_all_with_data(self, client, sample_list):
        """Should return all lists."""
        response = client.get("/api/lists")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestGetList:
    """Tests for GET /api/lists/{list_id}."""

    def test_get_list_success(self, client, sample_list):
        """Should return list by ID."""
        response = client.get(f"/api/lists/{sample_list}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_list

    def test_get_list_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.get("/api/lists/9999")
        assert response.status_code == 404


class TestUpdateList:
    """Tests for PUT /api/lists/{list_id}."""

    def test_update_list_name(self, client, sample_list):
        """Should update list name."""
        response = client.put(
            f"/api/lists/{sample_list}", json={"name": "Updated Name"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_update_list_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.put("/api/lists/9999", json={"name": "Test"})
        assert response.status_code == 404

    def test_update_list_no_data(self, client, sample_list):
        """Should reject empty update."""
        response = client.put(f"/api/lists/{sample_list}", json={})
        assert response.status_code == 400

    def test_update_list_invalid_profile(self, client, sample_list):
        """Should reject non-existent profile."""
        response = client.put(f"/api/lists/{sample_list}", json={"profile_id": 9999})
        assert response.status_code == 404


class TestDeleteList:
    """Tests for DELETE /api/lists/{list_id}."""

    @patch("app.routes.lists.threading.Thread")
    def test_delete_list_success(self, mock_thread, client, sample_list):
        """Should accept deletion request (async)."""
        response = client.delete(f"/api/lists/{sample_list}")
        # Returns 202 Accepted for async deletion
        assert response.status_code == 202
        data = response.json()
        assert "message" in data
        # Verify background thread was started
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_delete_list_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.delete("/api/lists/9999")
        assert response.status_code == 404

    def test_delete_list_already_deleting(self, client, db_session, sample_list):
        """Should reject deletion when already deleting."""
        from app.models import VideoList

        video_list = db_session.query(VideoList).get(sample_list)
        video_list.deleting = True
        db_session.commit()
        response = client.delete(f"/api/lists/{sample_list}")
        assert response.status_code == 409


class TestGetListTasks:
    """Tests for GET /api/lists/{list_id}/tasks."""

    def test_get_list_tasks_success(self, client, sample_list, sample_task):
        """Should return paginated tasks for a list."""
        response = client.get(f"/api/lists/{sample_list}/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)

    def test_get_list_tasks_empty(self, client, sample_list):
        """Should return empty paginated response when no tasks."""
        response = client.get(f"/api/lists/{sample_list}/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0


class TestGetListHistory:
    """Tests for GET /api/lists/{list_id}/history."""

    def test_get_list_history_success(self, client, sample_list):
        """Should return paginated history for a list."""
        response = client.get(f"/api/lists/{sample_list}/history")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data
        assert isinstance(data["entries"], list)

    def test_get_list_history_empty(self, client, sample_list):
        """Should return empty paginated response when no history."""
        response = client.get(f"/api/lists/{sample_list}/history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["entries"], list)


class TestGetListVideos:
    """Tests for GET /api/lists/{list_id}/videos."""

    def test_get_videos_page_success(self, client, sample_list, sample_video):
        """Should return paginated videos for a list."""
        response = client.get(f"/api/lists/{sample_list}/videos")

        assert response.status_code == 200
        data = response.json()
        assert "videos" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert len(data["videos"]) == 1

    def test_get_videos_page_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.get("/api/lists/9999/videos")

        assert response.status_code == 404

    def test_get_videos_page_filter_downloaded(self, client, sample_list, sample_video):
        """Should filter by downloaded status."""
        response = client.get(f"/api/lists/{sample_list}/videos?downloaded=false")

        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) == 1

    def test_get_videos_page_filter_failed(self, client, sample_list, sample_video):
        """Should filter by failed status."""
        response = client.get(f"/api/lists/{sample_list}/videos?failed=false")

        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) == 1

    def test_get_videos_page_pagination(self, client, sample_list, sample_video):
        """Should support pagination parameters."""
        response = client.get(f"/api/lists/{sample_list}/videos?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10


class TestGetListVideoStats:
    """Tests for GET /api/lists/{list_id}/videos/stats."""

    def test_get_stats_success(self, client, sample_list, sample_video):
        """Should return video statistics for a list."""
        response = client.get(f"/api/lists/{sample_list}/videos/stats")

        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "tasks" in data
        assert data["stats"]["total"] == 1
        assert data["stats"]["downloaded"] == 0
        assert data["stats"]["pending"] == 1

    def test_get_stats_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.get("/api/lists/9999/videos/stats")

        assert response.status_code == 404


class TestGetListVideosByIds:
    """Tests for GET /api/lists/{list_id}/videos/by-ids."""

    def test_get_videos_by_ids_success(self, client, sample_list, sample_video):
        """Should return videos by IDs."""
        response = client.get(
            f"/api/lists/{sample_list}/videos/by-ids?ids={sample_video}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_video

    def test_get_videos_by_ids_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.get("/api/lists/9999/videos/by-ids?ids=1")

        assert response.status_code == 404

    def test_get_videos_by_ids_invalid_format(self, client, sample_list):
        """Should return 400 for invalid ID format."""
        response = client.get(f"/api/lists/{sample_list}/videos/by-ids?ids=invalid")

        assert response.status_code == 400

    def test_get_videos_by_ids_empty(self, client, sample_list):
        """Should return empty list for empty IDs."""
        response = client.get(f"/api/lists/{sample_list}/videos/by-ids?ids=")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_videos_by_ids_max_limit(self, client, sample_list):
        """Should reject more than 100 IDs."""
        ids = ",".join(str(i) for i in range(101))
        response = client.get(f"/api/lists/{sample_list}/videos/by-ids?ids={ids}")

        assert response.status_code == 400


class TestSearchListVideos:
    """Tests for GET /api/lists/{list_id}/videos?search=..."""

    def test_search_videos_success(self, client, sample_list, sample_video):
        """Should search videos by title."""
        response = client.get(f"/api/lists/{sample_list}/videos?search=Test")

        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) == 1
        assert data["videos"][0]["title"] == "Test Video"

    def test_search_videos_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.get("/api/lists/9999/videos?search=test")

        assert response.status_code == 404

    def test_search_videos_no_results(self, client, sample_list, sample_video):
        """Should return empty list when no matches."""
        response = client.get(f"/api/lists/{sample_list}/videos?search=nonexistent")

        assert response.status_code == 200
        assert response.json()["videos"] == []

    def test_search_videos_filter_downloaded(self, client, sample_list, sample_video):
        """Should filter by downloaded status."""
        response = client.get(
            f"/api/lists/{sample_list}/videos?search=Test&downloaded=false"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) == 1
