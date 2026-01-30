"""Tests for profile API endpoints."""

from app.models.profile import Profile


class TestProfileToYtDlpOpts:
    """Tests for Profile.to_yt_dlp_opts() method."""

    def test_default_format_no_resolution(self, db_session):
        """Should use best format when no resolution or codec is set."""
        profile = Profile(name="Default")
        opts = profile.to_yt_dlp_opts()

        assert opts["format"] == "bv*+ba/best"
        assert opts["merge_output_format"] == "mp4"

    def test_resolution_limited_format(self, db_session):
        """Should limit format to specified resolution."""
        profile = Profile(name="1080p", preferred_resolution=1080)
        opts = profile.to_yt_dlp_opts()

        assert opts["format"] == "bv*[height<=1080]+ba/best[height<=1080]"

    def test_audio_only_mode(self, db_session):
        """Should use audio-only format when resolution is 0."""
        profile = Profile(name="Audio Only", preferred_resolution=0)
        opts = profile.to_yt_dlp_opts()

        assert opts["format"] == "bestaudio/best"
        assert opts["final_ext"] == "m4a"
        assert "merge_output_format" not in opts

        # Should have FFmpegExtractAudio postprocessor
        extract_audio = next(
            (p for p in opts["postprocessors"] if p["key"] == "FFmpegExtractAudio"),
            None,
        )
        assert extract_audio is not None
        assert extract_audio["preferredcodec"] == "m4a"

    def test_video_codec_preference(self, db_session):
        """Should add video codec filter to format string."""
        profile = Profile(name="AV1", preferred_video_codec="av01")
        opts = profile.to_yt_dlp_opts()

        assert "vcodec^=av01" in opts["format"]

    def test_audio_codec_preference(self, db_session):
        """Should use audio codec in format string."""
        profile = Profile(name="Opus", preferred_audio_codec="opus")
        opts = profile.to_yt_dlp_opts()

        assert "ba[acodec=opus]" in opts["format"]

    def test_combined_codec_preferences(self, db_session):
        """Should include video codec and audio codec in format string."""
        profile = Profile(
            name="Custom Codecs",
            preferred_video_codec="h265",
            preferred_audio_codec="flac",
        )
        opts = profile.to_yt_dlp_opts()

        assert "vcodec^=h265" in opts["format"]
        assert "ba[acodec=flac]" in opts["format"]

    def test_custom_output_format(self, db_session):
        """Should use custom output format when specified."""
        profile = Profile(name="MP4", output_format="mp4")
        opts = profile.to_yt_dlp_opts()

        assert opts["merge_output_format"] == "mp4"

    def test_audio_only_ignores_video_codec(self, db_session):
        """Audio-only mode should not include video codec preferences."""
        profile = Profile(
            name="Audio Only with Codec",
            preferred_resolution=0,
            preferred_video_codec="av01",
        )
        opts = profile.to_yt_dlp_opts()

        assert "format_sort" not in opts
        assert opts["format"] == "bestaudio/best"

    def test_resolution_with_codecs(self, db_session):
        """Should combine resolution limit with codec preferences."""
        profile = Profile(
            name="4K AV1",
            preferred_resolution=2160,
            preferred_video_codec="av01",
            preferred_audio_codec="opus",
        )
        opts = profile.to_yt_dlp_opts()

        assert (
            opts["format"]
            == "bv*[height<=2160][vcodec^=av01]+ba[acodec=opus]/bv*[height<=2160][vcodec^=av01]+ba/best[height<=2160]"
        )

    def test_extra_args_adds_new_options(self, db_session):
        """Should add new options from extra_args."""
        profile = Profile(
            name="With Extra Args",
            extra_args={"cookiefile": "/path/to/cookies.txt", "geo_bypass": True},
        )
        opts = profile.to_yt_dlp_opts()

        assert opts["cookiefile"] == "/path/to/cookies.txt"
        assert opts["geo_bypass"] is True

    def test_extra_args_does_not_overwrite_existing(self, db_session):
        """Should not overwrite existing profile options with extra_args."""
        profile = Profile(
            name="No Overwrite",
            extra_args={"format": "worst", "retries": 999},
        )
        opts = profile.to_yt_dlp_opts()

        # format and retries are set by the profile, should not be overwritten
        assert opts["format"] == "bv*+ba/best"
        assert opts["retries"] == 10

    def test_extra_args_empty_dict(self, db_session):
        """Should handle empty extra_args dict."""
        profile = Profile(name="Empty Extra Args", extra_args={})
        opts = profile.to_yt_dlp_opts()

        assert "format" in opts  # Normal options should still work

    def test_extra_args_none(self, db_session):
        """Should handle None extra_args."""
        profile = Profile(name="None Extra Args", extra_args=None)
        opts = profile.to_yt_dlp_opts()

        assert "format" in opts  # Normal options should still work

    def test_windows_filenames_enabled(self, db_session):
        """Should add windowsfilenames option when enabled."""
        profile = Profile(name="Windows Filenames", windows_filenames=True)
        opts = profile.to_yt_dlp_opts()

        assert opts["windowsfilenames"] is True

    def test_windows_filenames_disabled(self, db_session):
        """Should not add windowsfilenames option when disabled."""
        profile = Profile(name="No Windows Filenames", windows_filenames=False)
        opts = profile.to_yt_dlp_opts()

        assert "windowsfilenames" not in opts

    def test_restrict_filenames_enabled(self, db_session):
        """Should add restrictfilenames option when enabled."""
        profile = Profile(name="Restrict Filenames", restrict_filenames=True)
        opts = profile.to_yt_dlp_opts()

        assert opts["restrictfilenames"] is True

    def test_restrict_filenames_disabled(self, db_session):
        """Should not add restrictfilenames option when disabled."""
        profile = Profile(name="No Restrict Filenames", restrict_filenames=False)
        opts = profile.to_yt_dlp_opts()

        assert "restrictfilenames" not in opts

    def test_both_filename_options_enabled(self, db_session):
        """Should add both filename options when enabled."""
        profile = Profile(
            name="Both Filename Options",
            windows_filenames=True,
            restrict_filenames=True,
        )
        opts = profile.to_yt_dlp_opts()

        assert opts["windowsfilenames"] is True
        assert opts["restrictfilenames"] is True

    def test_filename_options_with_audio_only(self, db_session):
        """Filename options should work with audio-only mode."""
        profile = Profile(
            name="Audio Only with Filename Options",
            preferred_resolution=0,
            windows_filenames=True,
            restrict_filenames=True,
        )
        opts = profile.to_yt_dlp_opts()

        assert opts["format"] == "bestaudio/best"
        assert opts["windowsfilenames"] is True
        assert opts["restrictfilenames"] is True

    def test_date_metadata_parser_postprocessor(self, db_session):
        """Should include MetadataParser postprocessor for date parsing."""
        from yt_dlp.postprocessor.metadataparser import MetadataParserPP

        profile = Profile(name="Date Parser Test")
        opts = profile.to_yt_dlp_opts()

        metadata_parser = next(
            (p for p in opts["postprocessors"] if p["key"] == "MetadataParser"),
            None,
        )
        assert metadata_parser is not None
        assert metadata_parser["when"] == "pre_process"
        assert metadata_parser["actions"] == [
            (
                MetadataParserPP.interpretter,
                "%(upload_date>%Y-%m-%d|)s",
                "%(meta_date)s",
            )
        ]

    def test_date_metadata_parser_runs_at_pre_process(self, db_session):
        """MetadataParser should run at pre_process stage."""
        profile = Profile(name="Date Parser Order Test", embed_metadata=True)
        opts = profile.to_yt_dlp_opts()

        metadata_parser = next(
            (p for p in opts["postprocessors"] if p["key"] == "MetadataParser"),
            None,
        )
        assert metadata_parser is not None
        # pre_process ensures it runs before other postprocessors regardless of list order
        assert metadata_parser["when"] == "pre_process"

    def test_date_metadata_parser_with_audio_only(self, db_session):
        """MetadataParser should be included in audio-only mode."""
        profile = Profile(name="Audio Date Parser", preferred_resolution=0)
        opts = profile.to_yt_dlp_opts()

        metadata_parser = next(
            (p for p in opts["postprocessors"] if p["key"] == "MetadataParser"),
            None,
        )
        assert metadata_parser is not None


class TestProfileOptions:
    """Tests for GET /api/profiles/options."""

    def test_get_options_returns_defaults(self, client):
        """Should return profile defaults and sponsorblock configuration."""
        response = client.get("/api/profiles/options")

        assert response.status_code == 200
        data = response.json()
        assert "defaults" in data
        assert "sponsorblock" in data
        assert "resolutions" in data
        assert "video_codecs" in data
        assert "audio_codecs" in data

    def test_get_options_contains_include_live_default(self, client):
        """Should include include_live in defaults."""
        response = client.get("/api/profiles/options")

        data = response.json()
        assert "include_live" in data["defaults"]
        assert data["defaults"]["include_live"] is True

    def test_get_options_contains_filename_options_defaults(self, client):
        """Should include filename options in defaults."""
        response = client.get("/api/profiles/options")

        data = response.json()
        assert "windows_filenames" in data["defaults"]
        assert "restrict_filenames" in data["defaults"]
        assert data["defaults"]["windows_filenames"] is False
        assert data["defaults"]["restrict_filenames"] is False

    def test_get_options_contains_sponsorblock_behaviours(self, client):
        """Should include all sponsorblock behaviour options."""
        response = client.get("/api/profiles/options")

        data = response.json()
        behaviours = data["sponsorblock"]["behaviours"]
        assert "disabled" in behaviours
        assert "delete" in behaviours
        assert "mark_chapter" in behaviours

    def test_get_options_contains_resolutions(self, client):
        """Should include resolution options."""
        response = client.get("/api/profiles/options")

        data = response.json()
        assert "resolutions" in data
        resolutions = data["resolutions"]
        assert len(resolutions) > 0
        # Check audio-only option exists
        audio_only = next((r for r in resolutions if r["value"] == 0), None)
        assert audio_only is not None
        assert audio_only["label"] == "Audio Only"

    def test_get_options_contains_codecs(self, client):
        """Should include video and audio codec options."""
        response = client.get("/api/profiles/options")

        data = response.json()
        assert "video_codecs" in data
        assert "audio_codecs" in data
        assert len(data["video_codecs"]) > 0
        assert len(data["audio_codecs"]) > 0


class TestCreateProfile:
    """Tests for POST /api/profiles."""

    def test_create_profile_success(self, client):
        """Should create a profile with valid data."""
        response = client.post(
            "/api/profiles",
            json={"name": "My Profile"},
        )

        assert response.status_code == 201
        data = response.json()
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
                "sponsorblock_behaviour": "delete",
                "sponsorblock_categories": ["sponsor", "intro"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["sponsorblock_behaviour"] == "delete"
        assert data["sponsorblock_categories"] == ["sponsor", "intro"]

    def test_create_profile_with_include_live_false(self, client):
        """Should create profile with include_live disabled."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "No Live Profile",
                "include_live": False,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["include_live"] is False

    def test_create_profile_include_live_defaults_true(self, client):
        """Should default include_live to True."""
        response = client.post(
            "/api/profiles",
            json={"name": "Default Live Profile"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["include_live"] is True

    def test_create_profile_invalid_sponsorblock_behaviour(self, client):
        """Should reject invalid sponsorblock behaviour."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Bad Profile",
                "sponsorblock_behaviour": "invalid",
            },
        )

        assert response.status_code == 400

    def test_create_profile_invalid_sponsorblock_category(self, client):
        """Should reject invalid sponsorblock category."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Bad Profile",
                "sponsorblock_categories": ["invalid_category"],
            },
        )

        assert response.status_code == 400

    def test_create_profile_with_preferred_resolution(self, client):
        """Should create profile with preferred resolution."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "1080p Profile",
                "preferred_resolution": 1080,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["preferred_resolution"] == 1080

    def test_create_profile_with_audio_only(self, client):
        """Should create profile with audio-only mode (resolution=0)."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Audio Only Profile",
                "preferred_resolution": 0,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["preferred_resolution"] == 0

    def test_create_profile_with_video_codec(self, client):
        """Should create profile with video codec preference."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "AV1 Profile",
                "preferred_video_codec": "av01",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["preferred_video_codec"] == "av01"

    def test_create_profile_with_audio_codec(self, client):
        """Should create profile with audio codec preference."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Opus Profile",
                "preferred_audio_codec": "opus",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["preferred_audio_codec"] == "opus"

    def test_create_profile_with_extra_args(self, client):
        """Should create profile with extra_args."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Extra Args Profile",
                "extra_args": {"cookiefile": "/path/to/cookies.txt"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["extra_args"] == {"cookiefile": "/path/to/cookies.txt"}

    def test_create_profile_extra_args_defaults_empty(self, client):
        """Should default extra_args to empty dict."""
        response = client.post(
            "/api/profiles",
            json={"name": "No Extra Args Profile"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["extra_args"] == {}

    def test_create_profile_with_windows_filenames(self, client):
        """Should create profile with windows_filenames enabled."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Windows Filenames Profile",
                "windows_filenames": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["windows_filenames"] is True

    def test_create_profile_with_restrict_filenames(self, client):
        """Should create profile with restrict_filenames enabled."""
        response = client.post(
            "/api/profiles",
            json={
                "name": "Restrict Filenames Profile",
                "restrict_filenames": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["restrict_filenames"] is True

    def test_create_profile_filename_options_default_false(self, client):
        """Should default filename options to False."""
        response = client.post(
            "/api/profiles",
            json={"name": "Default Filename Options Profile"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["windows_filenames"] is False
        assert data["restrict_filenames"] is False


class TestListProfiles:
    """Tests for GET /api/profiles."""

    def test_list_profiles_empty(self, client):
        """Should return empty list when no profiles exist."""
        response = client.get("/api/profiles")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_profiles_with_data(self, client, sample_profile):
        """Should return all profiles."""
        response = client.get("/api/profiles")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Profile"


class TestGetProfile:
    """Tests for GET /api/profiles/<id>."""

    def test_get_profile_success(self, client, sample_profile):
        """Should return profile by ID."""
        response = client.get(f"/api/profiles/{sample_profile}")

        assert response.status_code == 200
        data = response.json()
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
        assert response.json()["name"] == "Updated Name"

    def test_update_profile_include_live(self, client, sample_profile):
        """Should update include_live setting."""
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={"include_live": False},
        )

        assert response.status_code == 200
        assert response.json()["include_live"] is False

    def test_update_profile_not_found(self, client):
        """Should return 404 for non-existent profile."""
        response = client.put(
            "/api/profiles/9999",
            json={"name": "Test"},
        )

        assert response.status_code == 404

    def test_update_profile_resolution(self, client, sample_profile):
        """Should update preferred resolution."""
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={"preferred_resolution": 2160},
        )

        assert response.status_code == 200
        assert response.json()["preferred_resolution"] == 2160

    def test_update_profile_codecs(self, client, sample_profile):
        """Should update codec preferences."""
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={
                "preferred_video_codec": "h265",
                "preferred_audio_codec": "flac",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preferred_video_codec"] == "h265"
        assert data["preferred_audio_codec"] == "flac"

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

    def test_update_profile_extra_args(self, client, sample_profile):
        """Should update extra_args."""
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={"extra_args": {"geo_bypass": True, "sleep_interval": 5}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["extra_args"] == {"geo_bypass": True, "sleep_interval": 5}

    def test_update_profile_windows_filenames(self, client, sample_profile):
        """Should update windows_filenames setting."""
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={"windows_filenames": True},
        )

        assert response.status_code == 200
        assert response.json()["windows_filenames"] is True

    def test_update_profile_restrict_filenames(self, client, sample_profile):
        """Should update restrict_filenames setting."""
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={"restrict_filenames": True},
        )

        assert response.status_code == 200
        assert response.json()["restrict_filenames"] is True

    def test_update_profile_both_filename_options(self, client, sample_profile):
        """Should update both filename options."""
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={
                "windows_filenames": True,
                "restrict_filenames": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["windows_filenames"] is True
        assert data["restrict_filenames"] is True


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
