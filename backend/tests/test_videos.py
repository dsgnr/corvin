"""Tests for video API endpoints."""


class TestListVideos:
    """Tests for GET /api/videos."""

    def test_list_videos_empty(self, client):
        """Should return empty list when no videos exist."""
        response = client.get("/api/videos")

        assert response.status_code == 200
        assert response.get_json() == []

    def test_list_videos_with_data(self, client, sample_video):
        """Should return all videos."""
        response = client.get("/api/videos")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1

    def test_list_videos_filter_by_list(self, client, sample_video, sample_list):
        """Should filter videos by list_id."""
        response = client.get(f"/api/videos?list_id={sample_list}")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1

    def test_list_videos_filter_by_downloaded(self, client, sample_video):
        """Should filter videos by downloaded status."""
        response = client.get("/api/videos?downloaded=false")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1

    def test_list_videos_pagination(self, client, sample_video):
        """Should support limit and offset."""
        response = client.get("/api/videos?limit=10&offset=0")

        assert response.status_code == 200


class TestGetVideo:
    """Tests for GET /api/videos/<id>."""

    def test_get_video_success(self, client, sample_video):
        """Should return video by ID."""
        response = client.get(f"/api/videos/{sample_video}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == sample_video
        assert data["title"] == "Test Video"

    def test_get_video_not_found(self, client):
        """Should return 404 for non-existent video."""
        response = client.get("/api/videos/9999")

        assert response.status_code == 404


class TestGetVideosByList:
    """Tests for GET /api/videos/list/<list_id>."""

    def test_get_videos_by_list_success(self, client, sample_list, sample_video):
        """Should return videos for a list."""
        response = client.get(f"/api/videos/list/{sample_list}")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1

    def test_get_videos_by_list_not_found(self, client):
        """Should return 404 for non-existent list."""
        response = client.get("/api/videos/list/9999")

        assert response.status_code == 404

    def test_get_videos_by_list_filter_downloaded(
        self, client, sample_list, sample_video
    ):
        """Should filter by downloaded status."""
        response = client.get(f"/api/videos/list/{sample_list}?downloaded=false")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1


class TestRetryVideo:
    """Tests for POST /api/videos/<id>/retry."""

    def test_retry_video_success(self, client, sample_video):
        """Should mark video for retry."""
        response = client.post(f"/api/videos/{sample_video}/retry")

        assert response.status_code == 200
        data = response.get_json()
        assert data["video"]["retry_count"] == 1

    def test_retry_video_not_found(self, client):
        """Should return 404 for non-existent video."""
        response = client.post("/api/videos/9999/retry")

        assert response.status_code == 404

    def test_retry_video_already_downloaded(self, client, app, sample_video):
        """Should reject retry for already downloaded video."""
        from app.extensions import db
        from app.models import Video

        with app.app_context():
            video = db.session.get(Video, sample_video)
            video.downloaded = True
            db.session.commit()

        response = client.post(f"/api/videos/{sample_video}/retry")

        assert response.status_code == 400
