"""Tests for error handlers."""


class TestErrorHandlers:
    """Tests for error handler routes."""

    def test_app_error_handler(self, client, app):
        """Should handle AppError and return JSON response."""
        # Trigger a NotFoundError via API
        response = client.get("/api/profiles/99999")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_validation_error_handler(self, client):
        """Should handle ValidationError with 400 status."""
        response = client.post("/api/profiles", json={})

        assert response.status_code == 400

    def test_conflict_error_handler(self, client, sample_profile):
        """Should handle ConflictError with 409 status."""
        response = client.post("/api/profiles", json={"name": "Test Profile"})

        assert response.status_code == 409

    def test_404_for_unknown_route(self, client):
        """Should return 404 for unknown routes."""
        response = client.get("/api/nonexistent")

        assert response.status_code == 404
