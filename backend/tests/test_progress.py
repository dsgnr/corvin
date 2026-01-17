"""Tests for progress API endpoints."""

from unittest.mock import patch


class TestGetProgress:
    """Tests for GET /api/progress."""

    @patch("app.services.progress_service.get_all")
    def test_get_progress_json(self, mock_get_all, client):
        """Should return progress as JSON."""
        mock_get_all.return_value = {
            1: {"video_id": 1, "status": "downloading", "percent": 50.0}
        }

        response = client.get("/api/progress")

        assert response.status_code == 200
        data = response.get_json()
        assert "1" in data or 1 in data

    @patch("app.services.progress_service.get_all")
    def test_get_progress_empty(self, mock_get_all, client):
        """Should return empty dict when no downloads active."""
        mock_get_all.return_value = {}

        response = client.get("/api/progress")

        assert response.status_code == 200
        assert response.get_json() == {}
