"""Tests for history API endpoints."""


class TestGetHistory:
    """Tests for GET /api/history."""

    def test_get_history_empty(self, client):
        """Should return empty paginated response when no history exists."""
        response = client.get("/api/history")

        assert response.status_code == 200
        data = response.json()
        assert data["entries"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["total_pages"] == 1

    def test_get_history_with_data(self, client, sample_history):
        """Should return all history entries."""
        response = client.get("/api/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 2
        assert data["total"] == 2

    def test_get_history_filter_by_entity_type(self, client, sample_history):
        """Should filter history by entity_type."""
        response = client.get("/api/history?entity_type=profile")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["entity_type"] == "profile"
        assert data["total"] == 1

    def test_get_history_filter_by_action(self, client, sample_history):
        """Should filter history by action."""
        response = client.get("/api/history?action=list_created")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["action"] == "list_created"
        assert data["total"] == 1

    def test_get_history_pagination(self, client, sample_history):
        """Should support page and page_size."""
        response = client.get("/api/history?page=1&page_size=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 1
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 1
        assert data["total_pages"] == 2

    def test_get_history_combined_filters(self, client, sample_history):
        """Should support multiple filters."""
        response = client.get("/api/history?entity_type=profile&action=profile_created")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 1
        assert data["total"] == 1

    def test_get_history_search(self, client, sample_history):
        """Should support search filter."""
        response = client.get("/api/history?search=profile")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["entity_type"] == "profile"
