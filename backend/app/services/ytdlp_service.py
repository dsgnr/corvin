from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import yt_dlp

from app.core.logging import get_logger
from app.models import Profile, Video

logger = get_logger("ytdlp")

MAX_METADATA_WORKERS = 5 # experimental amount


class YtDlpService:
    DEFAULT_OUTPUT_DIR = Path("/downloads")

    @classmethod
    def extract_info(cls, url: str, from_date: datetime | None = None) -> list[dict]:
        """Extract video information from a URL (channel/playlist) using parallel fetching."""
        logger.info("Extracting info from: %s", url)

        # Fast flat extraction to get video IDs
        video_urls = cls._extract_flat_playlist(url)
        if not video_urls:
            return []

        logger.info("Found %d videos, fetching metadata in parallel...", len(video_urls))

        # Fetch full metadata in parallel using the urls from above
        videos = cls._fetch_metadata_parallel(video_urls, from_date)

        logger.info("Extracted %d videos from %s", len(videos), url)
        return videos

    @classmethod
    def _extract_flat_playlist(cls, url: str) -> list[str]:
        """Extract video URLs from a playlist/channel without full metadata."""
        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error("Failed to extract flat playlist from %s: %s", url, e)
            raise

        if not info:
            logger.warning("No info returned for URL: %s", url)
            return []

        # My understanding...
        # There are two ways in which we'll receive entries from yt-dlp.
        # Sometimes the `entries` key will contain the list of videos.
        # Othertimes, perhaps newer channels(?), we'll contain two playlist types (videos/shorts). 
        # In these playlist types, there'll be a nested `entries` key.
        # It seems the cleanest way to determine this is by the presence (or lack) of an `entries` key.
        # If the list contains nested entry groups (items with an 'entries' key),
        # flatten and return all of their entries; otherwise, return the list as-is
        # If none of the items have an 'entries' key, return as-is
        entries = info.get("entries", [])

        # Handle nested entries (videos/shorts playlists)
        if any(entry and "entries" in entry for entry in entries if entry):
            flattened = []
            for entry in entries:
                if entry and "entries" in entry:
                    flattened.extend(entry["entries"])
            entries = flattened

        # Build video URLs from IDs
        video_urls = []
        for entry in entries:
            if not entry:
                continue
            video_id = entry.get("id")
            if video_id:
                video_urls.append(f"https://www.youtube.com/watch?v={video_id}")

        return video_urls

    @classmethod
    def _fetch_metadata_parallel(
        cls, video_urls: list[str], from_date: datetime | None
    ) -> list[dict]:
        """Fetch full metadata for videos in parallel."""
        from_date_str = from_date.strftime("%Y%m%d") if from_date else None
        results = []

        with ThreadPoolExecutor(max_workers=MAX_METADATA_WORKERS) as executor:
            futures = {
                executor.submit(cls._fetch_single_video, url, from_date_str): url
                for url in video_urls
            }

            for future in as_completed(futures):
                try:
                    video = future.result()
                    if video:
                        results.append(video)
                except Exception as e:
                    url = futures[future]
                    logger.warning("Failed to fetch metadata for %s: %s", url, e)

        return results

    @classmethod
    def _fetch_single_video(cls, url: str, from_date_str: str | None) -> dict | None:
        """Fetch full metadata for a single video, filtering by date if specified."""
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "nopart": True,
            "fragment_retries": 10,
            "retries": 10
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                return None

            # Filter by date if specified
            upload_date = info.get("upload_date")
            if from_date_str and upload_date and upload_date < from_date_str:
                return None

            return cls._parse_single_entry(info)

        except Exception as e:
            logger.debug("Error fetching %s: %s", url, e)
            return None

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
            "description": entry.get("description"),
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
        template = profile.output_template or "%(uploader)s/%(title)s.%(ext)s"
        output_template = str(cls.DEFAULT_OUTPUT_DIR / template)
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
