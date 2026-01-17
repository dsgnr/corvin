"""Tests for history API endpoints."""


class TestGetHistory:
    """Tests for GET /api/history."""

    def test_get_history_empty(self, client):
        """Should return empty list when no history exists."""
        response = client.get("/api/history")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_history_with_data(self, client, sample_history):
        """Should return all history entries."""
        response = client.get("/api/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_history_filter_by_entity_type(self, client, sample_history):
        """Should filter history by entity_type."""
        response = client.get("/api/history?entity_type=profile")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["entity_type"] == "profile"

    def test_get_history_filter_by_action(self, client, sample_history):
        """Should filter history by action."""
        response = client.get("/api/history?action=list_created")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["action"] == "list_created"

    def test_get_history_pagination(self, client, sample_history):
        """Should support limit and offset."""
        response = client.get("/api/history?limit=1&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_get_history_combined_filters(self, client, sample_history):
        """Should support multiple filters."""
        response = client.get("/api/history?entity_type=profile&action=profile_created")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
