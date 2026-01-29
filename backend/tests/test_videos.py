"""Tests for single video API endpoints."""


class TestGetVideo:
    """Tests for GET /api/videos/{video_id}."""

    def test_get_video_success(self, client, sample_video):
        """Should return video by ID."""
        response = client.get(f"/api/videos/{sample_video}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_video
        assert data["title"] == "Test Video"

    def test_get_video_not_found(self, client):
        """Should return 404 for non-existent video."""
        response = client.get("/api/videos/9999")

        assert response.status_code == 404


class TestRetryVideo:
    """Tests for POST /api/videos/{video_id}/retry."""

    def test_retry_video_success(self, client, sample_video):
        """Should mark video for retry."""
        response = client.post(f"/api/videos/{sample_video}/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["video"]["retry_count"] == 1

    def test_retry_video_not_found(self, client):
        """Should return 404 for non-existent video."""
        response = client.post("/api/videos/9999/retry")

        assert response.status_code == 404

    def test_retry_video_already_downloaded(self, client, db_session, sample_video):
        """Should reject retry for already downloaded video."""
        from app.models import Video

        video = db_session.query(Video).get(sample_video)
        video.downloaded = True
        db_session.commit()

        response = client.post(f"/api/videos/{sample_video}/retry")

        assert response.status_code == 400


class TestToggleBlacklist:
    """Tests for POST /api/videos/{video_id}/blacklist."""

    def test_toggle_blacklist_on(self, client, sample_video):
        """Should blacklist a video."""
        response = client.post(f"/api/videos/{sample_video}/blacklist")

        assert response.status_code == 200
        data = response.json()
        assert data["blacklisted"] is True

    def test_toggle_blacklist_off(self, client, db_session, sample_video):
        """Should unblacklist a video."""
        from app.models import Video

        video = db_session.query(Video).get(sample_video)
        video.blacklisted = True
        db_session.commit()

        response = client.post(f"/api/videos/{sample_video}/blacklist")

        assert response.status_code == 200
        data = response.json()
        assert data["blacklisted"] is False

    def test_toggle_blacklist_not_found(self, client):
        """Should return 404 for non-existent video."""
        response = client.post("/api/videos/9999/blacklist")

        assert response.status_code == 404

    def test_toggle_blacklist_includes_list(self, client, sample_video):
        """Should include list info in response."""
        response = client.post(f"/api/videos/{sample_video}/blacklist")

        assert response.status_code == 200
        data = response.json()
        assert "list" in data
        assert data["list"] is not None


class TestVideoFilesize:
    """Tests for Video.filesize field."""

    def test_video_filesize_default_none(self, client, sample_video):
        """Should have filesize as None by default."""
        response = client.get(f"/api/videos/{sample_video}")

        assert response.status_code == 200
        data = response.json()
        assert data["filesize"] is None

    def test_video_filesize_stored(self, client, db_session, sample_video):
        """Should store and return filesize."""
        from app.models import Video

        video = db_session.query(Video).get(sample_video)
        video.filesize = 1024000
        db_session.commit()

        response = client.get(f"/api/videos/{sample_video}")

        assert response.status_code == 200
        data = response.json()
        assert data["filesize"] == 1024000

    def test_video_to_dict_includes_filesize(self, db_session, sample_video):
        """Video.to_dict should include filesize."""
        from app.models import Video

        video = db_session.query(Video).get(sample_video)
        video.filesize = 5000000
        db_session.commit()

        video_dict = video.to_dict()
        assert "filesize" in video_dict
        assert video_dict["filesize"] == 5000000
