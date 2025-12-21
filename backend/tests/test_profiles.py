"""Tests for profile API endpoints."""


class TestProfileOptions:
    """Tests for GET /api/profiles/options."""

    def test_get_options_returns_defaults(self, client):
        """Should return profile defaults and sponsorblock configuration."""
        response = client.get("/api/profiles/options")

        assert response.status_code == 200
        data = response.get_json()
        assert "defaults" in data
        assert "sponsorblock" in data
        assert "output_formats" in data

    def test_get_options_contains_sponsorblock_behaviours(self, client):
        """Should include all sponsorblock behaviour options."""
        response = client.get("/api/profiles/options")

        data = response.get_json()
        behaviours = data["sponsorblock"]["behaviors"]
        assert "disabled" in behaviours
        assert "delete" in behaviours
        assert "mark_chapter" in behaviours


class TestCreateProfile:
    """Tests for POST /api/profiles."""

    def test_create_profile_success(self, client):
        """Should create a profile with valid data."""
        response = client.post(
            "/api/profiles",
            json={"name": "My Profile"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "My Profile"
        assert "id" in data

    def test_create_profile_missing_name(self, client):
        """Should reject profile without name."""
        response = client.post("/api/profiles", json={})

        assert response.status_code == 400

    def test_create_profile_duplicate_name(self, client, sample_profile):
        """Should reject duplicate profile name."""
        response = client.post(
            "/api/profiles",
            json={"name": "Test Profile"},
        )

        assert response.status_code == 409

    def test_create_profile_with_sponsorblock(self, client):
        """Should create profile with sponsorblock settings."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Sponsorblock Profile",
                "sponsorblock_behavior": "delete",
                "sponsorblock_categories": "sponsor,intro",
            },
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["sponsorblock_behavior"] == "delete"

    def test_create_profile_invalid_sponsorblock_behaviour(self, client):
        """Should reject invalid sponsorblock behaviour."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Bad Profile",
                "sponsorblock_behavior": "invalid",
            },
        )

        assert response.status_code == 400

    def test_create_profile_invalid_sponsorblock_category(self, client):
        """Should reject invalid sponsorblock category."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Bad Profile",
                "sponsorblock_categories": "invalid_category",
            },
        )

        assert response.status_code == 400


class TestListProfiles:
    """Tests for GET /api/profiles."""

    def test_list_profiles_empty(self, client):
        """Should return empty list when no profiles exist."""
        response = client.get("/api/profiles")

        assert response.status_code == 200
        assert response.get_json() == []

    def test_list_profiles_with_data(self, client, sample_profile):
        """Should return all profiles."""
        response = client.get("/api/profiles")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Profile"


class TestGetProfile:
    """Tests for GET /api/profiles/<id>."""

    def test_get_profile_success(self, client, sample_profile):
        """Should return profile by ID."""
        response = client.get(f"/api/profiles/{sample_profile}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == sample_profile

    def test_get_profile_not_found(self, client):
        """Should return 404 for non-existent profile."""
        response = client.get("/api/profiles/9999")

        assert response.status_code == 404


class TestUpdateProfile:
    """Tests for PUT /api/profiles/<id>."""

    def test_update_profile_name(self, client, sample_profile):
        """Should update profile name."""
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        assert response.get_json()["name"] == "Updated Name"

    def test_update_profile_not_found(self, client):
        """Should return 404 for non-existent profile."""
        response = client.put(
            "/api/profiles/9999",
            json={"name": "Test"},
        )

        assert response.status_code == 404

    def test_update_profile_no_data(self, client, sample_profile):
        """Should reject empty update."""
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={},
        )

        assert response.status_code == 400

    def test_update_profile_duplicate_name(self, client, sample_profile):
        """Should reject duplicate name on update."""
        # Create another profile
        client.post("/api/profiles", json={"name": "Other Profile"})

        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={"name": "Other Profile"},
        )

        assert response.status_code == 409


class TestDeleteProfile:
    """Tests for DELETE /api/profiles/<id>."""

    def test_delete_profile_success(self, client, sample_profile):
        """Should delete profile."""
        response = client.delete(f"/api/profiles/{sample_profile}")

        assert response.status_code == 204

    def test_delete_profile_not_found(self, client):
        """Should return 404 for non-existent profile."""
        response = client.delete("/api/profiles/9999")

        assert response.status_code == 404

    def test_delete_profile_with_lists(self, client, sample_list, sample_profile):
        """Should reject deletion when profile has associated lists."""
        response = client.delete(f"/api/profiles/{sample_profile}")

        assert response.status_code == 409
