"""
yt-dlp service for video extraction and downloading.

Wraps yt-dlp functionality for extracting metadata from channels/playlists
and downloading individual videos based on the list profile configuration.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

import requests
import yt_dlp

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.models import Profile, Video

logger = get_logger("ytdlp")

MAX_METADATA_WORKERS = 5  # Experimental amount

# Thumbnail ID to filename mapping for list artwork
THUMBNAIL_ARTWORK_MAP = {
    "banner_uncropped": "fanart.jpg",
    "avatar_uncropped": "poster.jpg",
    "0": "banner.jpg",
}

# Base yt-dlp options shared across all operations
_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
}

# Options for metadata extraction (no download)
_METADATA_OPTS = {
    **_BASE_OPTS,
    "skip_download": True,
    "retries": 10,
}

# Options for flat/quick extraction (just URLs, no full metadata)
_FLAT_EXTRACT_OPTS = {
    **_BASE_OPTS,
    "extract_flat": True,
    "ignoreerrors": True,
}


class YtDlpService:
    """
    Service for interacting with yt-dlp.
    """

    DEFAULT_OUTPUT_DIR = Path("/downloads")

    @classmethod
    def extract_list_metadata(cls, url: str) -> dict:
        """
        Extract channel/playlist metadata without fetching videos.

        Args:
            url: The channel or playlist URL.

        Returns:
            Dictionary with name, description, thumbnail, thumbnails, tags, extractor.

        Raises:
            Exception: If metadata extraction fails.
        """
        logger.info("Extracting metadata from: %s", url)

        ydl_opts = {
            **_METADATA_OPTS,
            "dump_single_json": True,
            "extract_flat": "in_playlist",
            "playlist_items": "0",
            "simulate": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error("Failed to extract metadata from %s: %s", url, e)
            raise

        if not info:
            logger.warning("No info returned for URL: %s", url)
            return {}

        thumbnails = info.get("thumbnails", [])

        return {
            "name": info.get("title") or info.get("channel") or info.get("uploader"),
            "description": info.get("description"),
            "thumbnail": cls._get_best_thumbnail(thumbnails),
            "thumbnails": thumbnails,
            "tags": info.get("tags", []),
            "extractor": info.get("extractor_key") or info.get("extractor"),
            "channel_id": info.get("channel_id")
            or info.get("uploader_id")
            or info.get("id"),
        }

    @classmethod
    def extract_videos(
        cls,
        url: str,
        from_date: datetime | None = None,
        on_video_fetched: Callable[[dict], None] | None = None,
        existing_video_ids: set[str] | None = None,
    ) -> list[dict]:
        """
        Extract video information from a channel or playlist URL.

        Uses parallel fetching for improved performance on large channels.

        Args:
            url: Channel or playlist URL.
            from_date: Only return videos uploaded on or after this date.
            on_video_fetched: Callback called for each video as it's fetched.
            existing_video_ids: Set of video IDs to skip (already in database).

        Returns:
            List of video dictionaries.
        """
        logger.info("Extracting videos from: %s", url)

        video_entries = cls._extract_video_entries(url)
        if not video_entries:
            return []

        if existing_video_ids:
            original_count = len(video_entries)
            video_entries = [
                e for e in video_entries if e["video_id"] not in existing_video_ids
            ]
            skipped = original_count - len(video_entries)
            if skipped > 0:
                logger.info("Skipped %d existing videos for %s", skipped, url)

        if not video_entries:
            logger.info("No new videos to fetch")
            return []

        logger.info(
            "Found %d new videos, fetching metadata in parallel...", len(video_entries)
        )

        video_urls = [e["url"] for e in video_entries]
        videos = cls._fetch_metadata_parallel(video_urls, from_date, on_video_fetched)

        logger.info("Extracted %d videos from %s", len(videos), url)
        return videos

    @classmethod
    def _extract_video_entries(cls, url: str) -> list[dict]:
        """
        Extract video entries (id + url) without full metadata.
        This is a super quick query in yt-dlp, so we use this to fetch the urls,
        then drop the full-fat gathering into threads.

        Works with any site supported by yt-dlp.

        Args:
            url: Channel or playlist URL.

        Returns:
            List of dicts with 'video_id' and 'url' keys.
        """
        ydl_opts = {**_FLAT_EXTRACT_OPTS}

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error("Failed to extract video URLs from %s: %s", url, e)
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

        if any(entry and "entries" in entry for entry in entries if entry):
            flattened = []
            for entry in entries:
                if entry and "entries" in entry:
                    flattened.extend(entry["entries"])
            entries = flattened

        video_entries = []
        for entry in entries:
            if not entry:
                continue
            video_id = entry.get("id")
            video_url = entry.get("webpage_url") or entry.get("url")
            if not video_url:
                logger.info("Skipping entry without URL: %s", entry.get("id"))
                continue
            video_entries.append({"video_id": video_id, "url": video_url})

        return video_entries

    @classmethod
    def _get_best_thumbnail(cls, thumbnails: list[dict]) -> str | None:
        """Get the best quality thumbnail URL from a list."""
        if not thumbnails:
            return None
        for thumb in reversed(thumbnails):
            if thumb.get("url"):
                return thumb["url"]
        return thumbnails[0].get("url") if thumbnails else None

    @classmethod
    def download_list_artwork(
        cls, thumbnails: list[dict], output_dir: Path
    ) -> dict[str, bool]:
        """
        Download list artwork (fanart, poster, banner) from thumbnails.
        - banner_uncropped -> fanart.jpg
        - avatar_uncropped -> poster.jpg
        - 0 -> banner.jpg

        Args:
            thumbnails: List of thumbnail dicts with 'id' and 'url' keys.
            output_dir: Directory to save the artwork files.

        Returns:
            Dictionary mapping filename to success status.
        """
        results = {}

        thumb_lookup = {}
        for thumb in thumbnails:
            thumb_id = thumb.get("id")
            thumb_url = thumb.get("url")
            if thumb_id is not None and thumb_url:
                thumb_lookup[str(thumb_id)] = thumb_url

        for thumb_id, filename in THUMBNAIL_ARTWORK_MAP.items():
            url = thumb_lookup.get(thumb_id)
            if not url:
                logger.info("Thumbnail ID '%s' not found in thumbnails", thumb_id)
                results[filename] = False
                continue

            output_path = output_dir / filename
            success = cls._download_image(url, output_path)
            results[filename] = success

        return results

    @classmethod
    def ensure_list_artwork(
        cls, list_name: str, list_url: str, metadata: dict | None = None
    ) -> None:
        """
        Ensure list artwork exists, downloading if missing.

        Checks for fanart.jpg, poster.jpg, banner.jpg and tvshow.nfo in the
        list's output directory. Downloads any missing files.

        Args:
            list_name: Name of the list (used for directory).
            list_url: URL of the list (used to fetch metadata if needed).
            metadata: Optional pre-fetched metadata dict. If not provided and
                     artwork is missing, metadata will be fetched from list_url.
        """
        if not list_name:
            return

        artwork_dir = cls.DEFAULT_OUTPUT_DIR / list_name
        artwork_files = ["fanart.jpg", "poster.jpg", "banner.jpg"]
        nfo_file = "tvshow.nfo"

        # Check what's missing
        missing_artwork = [f for f in artwork_files if not (artwork_dir / f).exists()]
        missing_nfo = not (artwork_dir / nfo_file).exists()

        if not missing_artwork and not missing_nfo:
            return  # Everything exists

        # Fetch metadata if not provided
        if metadata is None:
            logger.info(
                "Missing artwork for %s: %s - fetching metadata",
                list_name,
                missing_artwork or [nfo_file],
            )
            try:
                metadata = cls.extract_list_metadata(list_url)
            except Exception as e:
                logger.warning("Failed to fetch metadata for %s: %s", list_name, e)
                return

        thumbnails = metadata.get("thumbnails", [])

        # Download missing artwork
        if missing_artwork and thumbnails:
            try:
                results = cls.download_list_artwork(thumbnails, artwork_dir)
                downloaded = [f for f, ok in results.items() if ok]
                if downloaded:
                    logger.info("Downloaded artwork for %s: %s", list_name, downloaded)
            except Exception as e:
                logger.warning("Failed to download artwork for %s: %s", list_name, e)

        # Write NFO if missing
        if missing_nfo:
            try:
                cls.write_channel_nfo(metadata, artwork_dir, metadata.get("channel_id"))
            except Exception as e:
                logger.warning("Failed to write NFO for %s: %s", list_name, e)

    @classmethod
    def write_channel_nfo(
        cls, metadata: dict, output_dir: Path, channel_id: str | None = None
    ) -> bool:
        """
        Write a tvshow.nfo file for a channel/playlist.

        Args:
            metadata: Dictionary with name, description, tags, extractor.
            output_dir: Directory to save the tvshow.nfo file.
            channel_id: Platform-specific channel ID.

        Returns:
            True if successful, False otherwise.
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            root = ET.Element("tvshow")

            name = metadata.get("name", "Unknown")
            description = metadata.get("description") or ""
            extractor = (metadata.get("extractor") or "YouTube").lower()

            plot_elem = ET.SubElement(root, "plot")
            plot_elem.text = description
            outline_elem = ET.SubElement(root, "outline")
            outline_elem.text = description
            ET.SubElement(root, "lockdata").text = "false"
            ET.SubElement(root, "dateadded").text = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            ET.SubElement(root, "title").text = name
            ET.SubElement(root, "genre").text = extractor.capitalize()

            if channel_id:
                ET.SubElement(root, f"{extractor}id").text = channel_id

            art = ET.SubElement(root, "art")
            ET.SubElement(art, "poster").text = str(output_dir / "poster.jpg")
            ET.SubElement(art, "fanart").text = str(output_dir / "fanart.jpg")

            ET.SubElement(root, "season").text = "-1"
            ET.SubElement(root, "episode").text = "-1"

            unique_id = ET.SubElement(root, "uniqueid", type=extractor, default="true")
            unique_id.text = channel_id or name

            ET.indent(root)
            tree = ET.ElementTree(root)
            output_path = output_dir / "tvshow.nfo"
            tree.write(output_path, encoding="unicode", xml_declaration=True)

            logger.info("Wrote channel NFO: %s", output_path)
            return True

        except Exception as e:
            logger.warning("Failed to write channel NFO: %s", e)
            return False

    @classmethod
    def write_video_nfo(
        cls, video: Video, video_path: str, info: dict | None = None
    ) -> bool:
        """
        Write an NFO file for a downloaded video.

        Args:
            video: Video model instance.
            video_path: Path to the downloaded video file.
            info: Optional yt-dlp info dict for additional metadata.

        Returns:
            True if successful, False otherwise.
        """
        try:
            video_file = Path(video_path)
            nfo_path = video_file.with_suffix(".nfo")
            extractor = (video.extractor or "youtube").lower()

            root = ET.Element("episodedetails")

            description = video.description
            plot_elem = ET.SubElement(root, "plot")
            plot_elem.text = description
            outline_elem = ET.SubElement(root, "outline")
            outline_elem.text = description
            ET.SubElement(root, "lockdata").text = "false"
            ET.SubElement(root, "dateadded").text = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            ET.SubElement(root, "title").text = video.title

            if video.upload_date:
                ET.SubElement(root, "year").text = str(video.upload_date.year)
                ET.SubElement(root, "aired").text = video.upload_date.strftime(
                    "%Y-%m-%d"
                )
                ET.SubElement(root, "season").text = str(video.upload_date.year)

            if video.duration:
                ET.SubElement(root, "runtime").text = str(video.duration // 60)

            ET.SubElement(root, "country").text = ""
            ET.SubElement(root, "genre").text = extractor.capitalize()
            ET.SubElement(root, "studio").text = ""

            ET.SubElement(root, f"{extractor}id").text = video.video_id

            thumb_path = video_file.parent / f"{video_file.stem}-thumb.jpg"
            art = ET.SubElement(root, "art")
            ET.SubElement(art, "poster").text = str(thumb_path)

            if video.video_list:
                ET.SubElement(root, "showtitle").text = video.video_list.name

            ET.SubElement(root, "episode").text = str(
                abs(hash(video.video_id)) % 1000000
            )

            unique_id = ET.SubElement(root, "uniqueid", type=extractor, default="true")
            unique_id.text = video.video_id

            ET.indent(root)
            tree = ET.ElementTree(root)
            tree.write(nfo_path, encoding="unicode", xml_declaration=True)

            logger.info("Wrote video NFO: '%s'", nfo_path)
            return True

        except Exception as e:
            logger.warning("Failed to write video NFO for '%s': %s", video.title, e)
            return False

    @classmethod
    def _download_image(cls, url: str, output_path: Path) -> bool:
        """Download an image from URL to the specified path."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

            logger.info("Downloaded artwork: %s", output_path)
            return True

        except requests.RequestException as e:
            logger.warning("Failed to download image from %s: %s", url, e)
            return False
        except OSError as e:
            logger.warning("Failed to save image to %s: %s", output_path, e)
            return False

    @classmethod
    def _fetch_metadata_parallel(
        cls,
        video_urls: list[str],
        from_date: datetime | None,
        on_video_fetched: Callable[[dict], None] | None = None,
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
                        if on_video_fetched:
                            on_video_fetched(video)
                except Exception as e:
                    url = futures[future]
                    logger.warning("Failed to fetch metadata for %s: %s", url, e)

        return results

    @classmethod
    def _fetch_single_video(cls, url: str, from_date_str: str | None) -> dict | None:
        """Fetch full metadata for a single video, filtering by date if specified."""
        ydl_opts = {**_METADATA_OPTS}

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                return None

            upload_date = info.get("upload_date")
            if from_date_str and upload_date and upload_date < from_date_str:
                return None

            return cls._parse_single_entry(info)

        except Exception as e:
            logger.info("Error fetching %s: %s", url, e)
            return None

    @classmethod
    def _parse_single_entry(cls, entry: dict) -> dict | None:
        """Parse a single video entry from any supported site."""
        video_id = entry.get("id")
        if not video_id:
            return None

        upload_date = cls._parse_upload_date(entry.get("upload_date"))

        video_url = entry.get("webpage_url") or entry.get("url")
        if not video_url:
            logger.warning("No URL found for video: %s", video_id)
            return None

        return {
            "video_id": video_id,
            "title": entry.get("title") or "Unknown",
            "url": video_url,
            "duration": entry.get("duration"),
            "upload_date": upload_date,
            "thumbnail": entry.get("thumbnail"),
            "description": entry.get("description"),
            "extractor": entry.get("extractor_key") or entry.get("extractor"),
            "media_type": entry.get("media_type"),
            "was_live": entry.get("was_live", False),
        }

    @classmethod
    def _extract_labels(cls, info: dict) -> dict:
        """
        Extract video metadata labels from yt-dlp info dict.

        Extracts: container format, audio codec, resolution, audio channels,
        dynamic range, filesize.
        """
        labels = {}

        if ext := info.get("ext"):
            labels["format"] = ext

        if acodec := info.get("acodec"):
            labels["acodec"] = acodec

        if height := info.get("height"):
            labels["resolution"] = f"{height}p"

        if audio_channels := info.get("audio_channels"):
            labels["audio_channels"] = audio_channels

        if dynamic_range := info.get("dynamic_range"):
            labels["dynamic_range"] = dynamic_range

        if filesize := info.get("filesize_approx"):
            labels["filesize_approx"] = filesize

        if was_live := info.get("was_live"):
            labels["was_live"] = was_live

        return labels

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
        cls,
        video: Video,
        profile: Profile,
        output_dir: Path | None = None,
    ) -> tuple[bool, str, dict]:
        """
        Download a video using the specified profile settings.

        Args:
            video: Video model instance.
            profile: Profile with download settings.
            output_dir: Optional output directory override.

        Returns:
            Tuple of (success, filename_or_error, labels).
        """
        from app.services import progress_service

        output_template = str(cls.DEFAULT_OUTPUT_DIR / profile.output_template)
        ydl_opts = cls._build_download_opts(profile, output_template)
        ydl_opts["progress_hooks"] = [progress_service.create_hook(video.id)]

        logger.info("Downloading video: %s", video.title)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video.url, download=True)

                if not info:
                    msg = "Failed to extract video info."
                    progress_service.mark_error(video.id, msg)
                    return False, msg, {}

                filename = ydl.prepare_filename(info)
                labels = cls._extract_labels(info)

                cls.write_video_nfo(video, filename, info)
                progress_service.mark_done(video.id)

                logger.info("Downloaded: %s", filename)
                return True, filename, labels

        except yt_dlp.DownloadError as e:
            error_msg = str(e)
            logger.error("Download error for %s: %s", video.title, error_msg)
            progress_service.mark_error(video.id, error_msg)
            return False, error_msg, {}

        except Exception as e:
            error_msg = str(e)
            logger.exception("Unexpected error downloading %s", video.title)
            progress_service.mark_error(video.id, error_msg)
            return False, error_msg, {}

    @staticmethod
    def _build_download_opts(profile: Profile, output_template: str) -> dict:
        """Build yt-dlp options from profile."""
        opts = profile.to_yt_dlp_opts()
        opts.update(
            {
                **_BASE_OPTS,
                "outtmpl": output_template,
                "ignoreerrors": True,
                "fragment_retries": 10,
                "concurrent_fragment_downloads": 5,
                "writeinfojson": True,
                "format": "bv*+ba",
            }
        )
        return opts
