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
    """Tests for GET /api/lists/<id>."""

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

    def test_get_list_with_videos(self, client, sample_list, sample_video):
        """Should include videos when requested."""
        response = client.get(f"/api/lists/{sample_list}?include_videos=true")

        assert response.status_code == 200
        data = response.json()
        assert "videos" in data
        assert len(data["videos"]) == 1


class TestUpdateList:
    """Tests for PUT /api/lists/<id>."""

    def test_update_list_name(self, client, sample_list):
        """Should update list name."""
        response = client.put(
            f"/api/lists/{sample_list}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_update_list_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.put(
            "/api/lists/9999",
            json={"name": "Test"},
        )

        assert response.status_code == 404

    def test_update_list_no_data(self, client, sample_list):
        """Should reject empty update."""
        response = client.put(f"/api/lists/{sample_list}", json={})

        assert response.status_code == 400

    def test_update_list_invalid_profile(self, client, sample_list):
        """Should reject non-existent profile."""
        response = client.put(
            f"/api/lists/{sample_list}",
            json={"profile_id": 9999},
        )

        assert response.status_code == 404

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_update_list_duplicate_url(
        self, mock_enqueue, mock_metadata, client, sample_profile, sample_list
    ):
        """Should reject duplicate URL on update."""
        mock_metadata.return_value = {}

        # Create another list
        client.post(
            "/api/lists",
            json={
                "name": "Other List",
                "url": "https://youtube.com/c/other",
                "profile_id": sample_profile,
            },
        )

        response = client.put(
            f"/api/lists/{sample_list}",
            json={"url": "https://youtube.com/c/other"},
        )

        assert response.status_code == 409


class TestDeleteList:
    """Tests for DELETE /api/lists/<id>."""

    def test_delete_list_success(self, client, sample_list):
        """Should delete list."""
        response = client.delete(f"/api/lists/{sample_list}")

        assert response.status_code == 204

    def test_delete_list_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.delete("/api/lists/9999")

        assert response.status_code == 404

    def test_delete_list_cascades_videos(self, client, sample_list, sample_video):
        """Should delete associated videos."""
        response = client.delete(f"/api/lists/{sample_list}")

        assert response.status_code == 204

        # Verify video is gone
        video_response = client.get(f"/api/videos/{sample_video}")
        assert video_response.status_code == 404


class TestGetListTasks:
    """Tests for GET /api/lists/<id>/tasks."""

    def test_get_list_tasks_success(self, client, sample_list, sample_task):
        """Should return tasks for a list."""
        response = client.get(f"/api/lists/{sample_list}/tasks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_list_tasks_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.get("/api/lists/9999/tasks")

        assert response.status_code == 404

    def test_get_list_tasks_with_limit(self, client, sample_list):
        """Should respect limit parameter."""
        response = client.get(f"/api/lists/{sample_list}/tasks?limit=5")

        assert response.status_code == 200


class TestGetListHistory:
    """Tests for GET /api/lists/<id>/history."""

    def test_get_list_history_success(self, client, sample_list):
        """Should return history for a list."""
        response = client.get(f"/api/lists/{sample_list}/history")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_list_history_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.get("/api/lists/9999/history")

        assert response.status_code == 404


class TestGetListWithStats:
    """Tests for GET /api/lists/<id> with stats."""

    def test_get_list_with_stats(self, client, sample_list, sample_video):
        """Should include stats when requested."""
        response = client.get(f"/api/lists/{sample_list}?include_stats=true")

        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "total" in data["stats"]
        assert "downloaded" in data["stats"]
        assert "pending" in data["stats"]
