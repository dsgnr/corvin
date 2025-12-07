from datetime import datetime
from pathlib import Path

import yt_dlp

from app.core.logging import get_logger
from app.models import Profile, Video

logger = get_logger("ytdlp")


class YtDlpService:
    DEFAULT_OUTPUT_DIR = Path("downloads")

    @classmethod
    def extract_info(cls, url: str, from_date: datetime | None = None) -> list[dict]:
        """Extract video information from a URL (channel/playlist)."""
        logger.info("Extracting info from: %s", url)

        ydl_opts = {
            "quiet": False,
            "extract_flat": False,
            "ignoreerrors": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error("Failed to extract info from %s: %s", url, e)
            raise

        if not info:
            logger.warning("No info returned for URL: %s", url)
            return []

        entries = info.get("entries", [])
        # There are two ways in which we'll receive entries from yt-dlp.
        # Sometimes the `entries` key will contain the list of videos.
        # Othertimes, perhaps newer channels(?), we'll contain two playlist types (videos/shorts). In these playlist types, there'll be a nested `entries` key.
        # It seems the cleanest way to determine this is by the presence (or lack) of an `entries` key.

        # If the list contains nested entry groups (items with an 'entries' key),
        # flatten and return all of their entries; otherwise, return the list as-is

        # If none of the items have an 'entries' key, return as-is
        if not any("entries" in entry for entry in entries):
            results = entries
        else:
            # Flatten all nested entries
            results = []
            for entry in entries:
                if "entries" in entry:
                    results.extend(entry["entries"])


        videos = cls._parse_entries(results, from_date)

        logger.info("Found %d videos from %s", len(videos), url)
        return videos

    @classmethod
    def _parse_entries(cls, entries: list, from_date: datetime | None) -> list[dict]:
        """Parse video entries from yt-dlp response."""
        videos = []

        for entry in entries:
            if not entry:
                continue

            video = cls._parse_single_entry(entry)
            if not video:
                continue

            if from_date and video.get("upload_date"):
                if video["upload_date"] < from_date:
                    continue

            videos.append(video)

        return videos

    @classmethod
    def _parse_single_entry(cls, entry: dict) -> dict | None:
        """Parse a single video entry."""
        video_id = entry.get("id")
        if not video_id:
            return None

        upload_date = cls._parse_upload_date(entry.get("upload_date"))

        return {
            "video_id": video_id,
            "title": entry.get("title", "Unknown"),
            "url": (
                entry.get("url")
                or entry.get("webpage_url")
                or f"https://www.youtube.com/watch?v={video_id}"
            ),
            "duration": entry.get("duration"),
            "upload_date": upload_date,
            "thumbnail": entry.get("thumbnail"),
        }

    @staticmethod
    def _parse_upload_date(date_str: str | None) -> datetime | None:
        """Parse upload date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            return None

    @classmethod
    def download_video(
        cls, video: Video, profile: Profile, output_dir: Path | None = None
    ) -> tuple[bool, str]:
        """Download a video using the specified profile settings."""
        output_dir = output_dir or cls.DEFAULT_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use profile's output template or default
        template = profile.output_template or "%(uploader)s/%(title)s.%(ext)s"
        output_template = str(output_dir / template)
        ydl_opts = cls._build_download_opts(profile, output_template)

        logger.info("Downloading video: %s", video.title)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video.url, download=True)

                if not info:
                    return False, "Failed to extract video info"

                filename = ydl.prepare_filename(info)
                logger.info("Downloaded: %s", filename)
                return True, filename

        except yt_dlp.DownloadError as e:
            logger.error("Download error for %s: %s", video.title, e)
            return False, str(e)
        except Exception as e:
            logger.exception("Unexpected error downloading %s", video.title)
            return False, str(e)

    @staticmethod
    def _build_download_opts(profile: Profile, output_template: str) -> dict:
        """Build yt-dlp options from profile."""
        opts = profile.to_yt_dlp_opts()
        opts.update({
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
        })
        return opts
