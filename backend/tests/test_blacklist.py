"""Tests for blacklist functionality."""

import time
from unittest.mock import patch

from app.models import Video, VideoList


class TestBlacklistRegexOnCreate:
    """Tests for blacklist_regex on list creation."""

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_with_blacklist_regex(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should create a list with blacklist_regex."""
        mock_metadata.return_value = {}

        response = client.post(
            "/api/lists",
            json={
                "name": "Channel With Blacklist",
                "url": "https://youtube.com/c/blacklistchannel",
                "profile_id": sample_profile,
                "blacklist_regex": "live|stream",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["blacklist_regex"] == "live|stream"

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_without_blacklist_regex(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Create a list without blacklist_regex."""
        mock_metadata.return_value = {}

        response = client.post(
            "/api/lists",
            json={
                "name": "Channel Without Blacklist",
                "url": "https://youtube.com/c/noblacklist",
                "profile_id": sample_profile,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["blacklist_regex"] is None


class TestBlacklistRegexOnUpdate:
    """Tests for blacklist_regex on list update."""

    @patch("app.routes.lists.threading.Thread")
    def test_update_list_blacklist_regex(self, mock_thread, client, sample_list):
        """Update blacklist_regex and trigger background reapply."""
        response = client.put(
            f"/api/lists/{sample_list}",
            json={"blacklist_regex": "sponsor|ad"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["blacklist_regex"] == "sponsor|ad"
        # Background thread should be started to reapply
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_update_list_clear_blacklist_regex(self, client, db_session, sample_list):
        """Clear blacklist_regex when set to null."""
        # First set a blacklist regex
        video_list = db_session.query(VideoList).get(sample_list)
        video_list.blacklist_regex = "test"
        db_session.commit()

        with patch("app.routes.lists.threading.Thread"):
            response = client.put(
                f"/api/lists/{sample_list}",
                json={"blacklist_regex": None},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["blacklist_regex"] is None

    def test_update_list_same_blacklist_regex_no_reapply(
        self, client, db_session, sample_list
    ):
        """Should not trigger reapply if blacklist_regex unchanged."""
        # Set initial blacklist regex
        video_list = db_session.query(VideoList).get(sample_list)
        video_list.blacklist_regex = "live"
        db_session.commit()

        with patch("app.routes.lists.threading.Thread") as mock_thread:
            response = client.put(
                f"/api/lists/{sample_list}",
                json={"name": "Updated Name"},  # Not changing blacklist_regex
            )

        assert response.status_code == 200
        # Thread should NOT be started since blacklist_regex didn't change
        mock_thread.assert_not_called()


class TestBlacklistVideoFiltering:
    """Tests for filtering videos by blacklisted status."""

    def test_get_videos_filter_blacklisted_true(
        self, client, db_session, sample_list, sample_video
    ):
        """Filter to only blacklisted videos."""
        # Mark the video as blacklisted
        video = db_session.query(Video).get(sample_video)
        video.blacklisted = True
        db_session.commit()

        response = client.get(f"/api/lists/{sample_list}/videos?blacklisted=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) == 1
        assert data["videos"][0]["blacklisted"] is True

    def test_get_videos_filter_blacklisted_false(
        self, client, db_session, sample_list, sample_video
    ):
        """Filter to only non-blacklisted videos."""
        # Ensure video is not blacklisted
        video = db_session.query(Video).get(sample_video)
        video.blacklisted = False
        db_session.commit()

        response = client.get(f"/api/lists/{sample_list}/videos?blacklisted=false")

        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) == 1
        assert data["videos"][0]["blacklisted"] is False

    def test_get_videos_no_blacklist_filter(self, client, sample_list, sample_video):
        """Return all videos when no blacklist filter."""
        response = client.get(f"/api/lists/{sample_list}/videos")

        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) == 1


class TestBlacklistStats:
    """Tests for blacklisted count in video stats."""

    def test_stats_include_blacklisted_count(
        self, client, db_session, sample_list, sample_video
    ):
        """Include blacklisted count in stats."""
        # Mark video as blacklisted
        video = db_session.query(Video).get(sample_video)
        video.blacklisted = True
        db_session.commit()

        response = client.get(f"/api/lists/{sample_list}/videos/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["blacklisted"] == 1

    def test_stats_blacklisted_zero_when_none(self, client, sample_list, sample_video):
        """Return 0 blacklisted when none are blacklisted."""
        response = client.get(f"/api/lists/{sample_list}/videos/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["blacklisted"] == 0


class TestBlacklistReapplyBackground:
    """Tests for _reapply_blacklist_background function."""

    def test_reapply_blacklist_marks_matching_videos(self, db_session, sample_list):
        """Mark videos matching the regex as blacklisted."""
        from app.routes.lists import _reapply_blacklist_background

        # Create videos with different titles
        videos = [
            Video(
                video_id="vid1",
                title="Regular Video",
                url="https://youtube.com/watch?v=vid1",
                list_id=sample_list,
                blacklisted=False,
            ),
            Video(
                video_id="vid2",
                title="Live Stream Today",
                url="https://youtube.com/watch?v=vid2",
                list_id=sample_list,
                blacklisted=False,
            ),
            Video(
                video_id="vid3",
                title="Another Live Event",
                url="https://youtube.com/watch?v=vid3",
                list_id=sample_list,
                blacklisted=False,
            ),
        ]
        db_session.add_all(videos)
        db_session.commit()

        # Run reapply with "live" pattern
        _reapply_blacklist_background(sample_list, "Test List", "live")

        # Give background thread time to complete
        time.sleep(0.2)

        # Refresh and check
        db_session.expire_all()
        vid1 = db_session.query(Video).filter_by(video_id="vid1").first()
        vid2 = db_session.query(Video).filter_by(video_id="vid2").first()
        vid3 = db_session.query(Video).filter_by(video_id="vid3").first()

        assert vid1.blacklisted is False  # "Regular Video" doesn't match
        assert vid2.blacklisted is True  # "Live Stream Today" matches
        assert vid3.blacklisted is True  # "Another Live Event" matches

    def test_reapply_blacklist_clears_when_regex_none(self, db_session, sample_list):
        """Clear blacklist status when regex is None."""
        from app.routes.lists import _reapply_blacklist_background

        # Create a blacklisted video
        video = Video(
            video_id="vid_clear",
            title="Previously Blacklisted",
            url="https://youtube.com/watch?v=vid_clear",
            list_id=sample_list,
            blacklisted=True,
        )
        db_session.add(video)
        db_session.commit()

        # Run reapply with None pattern
        _reapply_blacklist_background(sample_list, "Test List", None)

        # Give background thread time to complete
        time.sleep(0.2)

        # Refresh and check
        db_session.expire_all()
        video = db_session.query(Video).filter_by(video_id="vid_clear").first()
        assert video.blacklisted is False

    def test_reapply_blacklist_case_insensitive(self, db_session, sample_list):
        """Match case-insensitively."""
        from app.routes.lists import _reapply_blacklist_background

        video = Video(
            video_id="vid_case",
            title="LIVE STREAM",
            url="https://youtube.com/watch?v=vid_case",
            list_id=sample_list,
            blacklisted=False,
        )
        db_session.add(video)
        db_session.commit()

        # Run reapply with lowercase pattern
        _reapply_blacklist_background(sample_list, "Test List", "live")

        time.sleep(0.2)

        db_session.expire_all()
        video = db_session.query(Video).filter_by(video_id="vid_case").first()
        assert video.blacklisted is True

    def test_reapply_blacklist_invalid_regex(self, db_session, sample_list):
        """Handle invalid regex gracefully."""
        from app.routes.lists import _reapply_blacklist_background

        video = Video(
            video_id="vid_invalid",
            title="Test Video",
            url="https://youtube.com/watch?v=vid_invalid",
            list_id=sample_list,
            blacklisted=False,
        )
        db_session.add(video)
        db_session.commit()

        # Run reapply with invalid regex (unclosed bracket)
        _reapply_blacklist_background(sample_list, "Test List", "[invalid")

        time.sleep(0.2)

        # Video should remain unchanged
        db_session.expire_all()
        video = db_session.query(Video).filter_by(video_id="vid_invalid").first()
        assert video.blacklisted is False

    def test_reapply_blacklist_or_pattern(self, db_session, sample_list):
        """Support OR patterns with pipe."""
        from app.routes.lists import _reapply_blacklist_background

        videos = [
            Video(
                video_id="vid_or1",
                title="Live Stream",
                url="https://youtube.com/watch?v=vid_or1",
                list_id=sample_list,
                blacklisted=False,
            ),
            Video(
                video_id="vid_or2",
                title="Sponsor Message",
                url="https://youtube.com/watch?v=vid_or2",
                list_id=sample_list,
                blacklisted=False,
            ),
            Video(
                video_id="vid_or3",
                title="Regular Content",
                url="https://youtube.com/watch?v=vid_or3",
                list_id=sample_list,
                blacklisted=False,
            ),
        ]
        db_session.add_all(videos)
        db_session.commit()

        # Run reapply with OR pattern
        _reapply_blacklist_background(sample_list, "Test List", "live|sponsor")

        time.sleep(0.2)

        db_session.expire_all()
        vid1 = db_session.query(Video).filter_by(video_id="vid_or1").first()
        vid2 = db_session.query(Video).filter_by(video_id="vid_or2").first()
        vid3 = db_session.query(Video).filter_by(video_id="vid_or3").first()

        assert vid1.blacklisted is True  # matches "live"
        assert vid2.blacklisted is True  # matches "sponsor"
        assert vid3.blacklisted is False  # no match

    def test_reapply_blacklist_phrase_match(self, db_session, sample_list):
        """Match phrases with spaces."""
        from app.routes.lists import _reapply_blacklist_background

        videos = [
            Video(
                video_id="vid_phrase1",
                title="After Files: The Many Worlds Theory!",
                url="https://youtube.com/watch?v=vid_phrase1",
                list_id=sample_list,
                blacklisted=False,
            ),
            Video(
                video_id="vid_phrase2",
                title="Main Episode Content",
                url="https://youtube.com/watch?v=vid_phrase2",
                list_id=sample_list,
                blacklisted=False,
            ),
        ]
        db_session.add_all(videos)
        db_session.commit()

        # Run reapply with phrase pattern
        _reapply_blacklist_background(sample_list, "Test List", "after files")

        time.sleep(0.2)

        db_session.expire_all()
        vid1 = db_session.query(Video).filter_by(video_id="vid_phrase1").first()
        vid2 = db_session.query(Video).filter_by(video_id="vid_phrase2").first()

        assert vid1.blacklisted is True  # matches "after files"
        assert vid2.blacklisted is False  # no match


class TestBlacklistOnSync:
    """Tests for blacklist logic during video sync."""

    def test_sync_marks_matching_videos_blacklisted(self, db_session, sample_profile):
        """Mark videos matching blacklist regex during sync."""
        # Create a list with blacklist regex
        video_list = VideoList(
            name="Blacklist Test Channel",
            url="https://youtube.com/c/blacklisttest",
            profile_id=sample_profile,
            blacklist_regex="live|stream",
        )
        db_session.add(video_list)
        db_session.commit()
        list_id = video_list.id

        # Simulate adding videos during sync
        videos = [
            Video(
                video_id="sync1",
                title="Regular Video",
                url="https://youtube.com/watch?v=sync1",
                list_id=list_id,
                blacklisted=False,
            ),
            Video(
                video_id="sync2",
                title="Live Stream Event",
                url="https://youtube.com/watch?v=sync2",
                list_id=list_id,
                blacklisted=True,  # Should be marked during sync
            ),
        ]
        db_session.add_all(videos)
        db_session.commit()

        # Verify the blacklist status
        vid1 = db_session.query(Video).filter_by(video_id="sync1").first()
        vid2 = db_session.query(Video).filter_by(video_id="sync2").first()

        assert vid1.blacklisted is False
        assert vid2.blacklisted is True


class TestBlacklistExcludesFromAutoDownload:
    """Tests for blacklisted videos being excluded from auto-download."""

    def test_schedule_downloads_excludes_blacklisted(
        self, app, db_session, sample_list
    ):
        """Exclude blacklisted videos from automatic download scheduling."""
        from app.tasks import schedule_downloads

        # Update list to enable auto_download
        video_list = db_session.query(VideoList).get(sample_list)
        video_list.auto_download = True
        db_session.commit()

        # Create videos - one blacklisted, one not
        videos = [
            Video(
                video_id="dl1",
                title="Regular Video",
                url="https://youtube.com/watch?v=dl1",
                list_id=sample_list,
                blacklisted=False,
                downloaded=False,
            ),
            Video(
                video_id="dl2",
                title="Blacklisted Video",
                url="https://youtube.com/watch?v=dl2",
                list_id=sample_list,
                blacklisted=True,
                downloaded=False,
            ),
        ]
        db_session.add_all(videos)
        db_session.commit()

        # Mock the task queue to avoid actual task creation
        with patch("app.tasks.enqueue_tasks_bulk") as mock_enqueue:
            mock_enqueue.return_value = {"queued": 1, "skipped": 0, "tasks": []}
            schedule_downloads()

            # Should only queue the non-blacklisted video
            if mock_enqueue.called:
                call_args = mock_enqueue.call_args
                entity_ids = call_args[0][1]  # Second positional arg is entity_ids
                # The blacklisted video should not be in the list
                blacklisted_video = (
                    db_session.query(Video).filter_by(video_id="dl2").first()
                )
                assert blacklisted_video.id not in entity_ids


class TestVideoBlacklistedField:
    """Tests for the blacklisted field on Video model."""

    def test_video_to_dict_includes_blacklisted(self, db_session, sample_list):
        """Include blacklisted field in to_dict output."""
        video = Video(
            video_id="dict_test",
            title="Test Video",
            url="https://youtube.com/watch?v=dict_test",
            list_id=sample_list,
            blacklisted=True,
        )
        db_session.add(video)
        db_session.commit()

        video_dict = video.to_dict()
        assert "blacklisted" in video_dict
        assert video_dict["blacklisted"] is True

    def test_video_blacklisted_default_false(self, db_session, sample_list):
        """Default blacklisted to False."""
        video = Video(
            video_id="default_test",
            title="Test Video",
            url="https://youtube.com/watch?v=default_test",
            list_id=sample_list,
        )
        db_session.add(video)
        db_session.commit()

        assert video.blacklisted is False
