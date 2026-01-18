#!/usr/bin/env python3
"""
Seed the database with dummy data for local performance testing.

This is a tool for making the FastAPI + SQLAlchemy backend work hard
enough that problems become obvious.
In my experience, if someone _can_ do something, they probably will.
So, if there's a YouTube channel with 5 million videos, no doubt someone will want
to sync it and store gigabytes of rows in an SQLite db.

I use this when I want the API to sit under constant write pressure while the UI
is loading large lists, opening detail pages, or holding open SSE connections. Most
of the interesting stuff (locks/readonly db etc) only show up once SQLite is
juggling concurrent readers and writers, so this script focuses on that.

A few intentional choices worth calling out for future-me:

- Each worker gets its own SQLAlchemy session. Nothing is shared across threads.
- Writes are committed in randomly sized batches to avoid a neat, predictable
  write pattern. Since we're using threads to fetch the yt-dlp,
  we'd be committing to the db randomly.
- Background sync workers are paused so they do not interfere with results.
  It's not real data, so we'll just fail fetching metadata anyway.

One practical note on scale: while the numbers used here look extreme, there *are*
real YouTube channels with millions of videos. I am not entirely sure why anyone
would want to download all of them, but it does mean that very large lists are not
purely made up. It is useful to know how the system behaves when a single list
grows to a genuinely ridiculous size.

Typical usage examples:

    # Create a few new lists and populate them concurrently
    python scripts/seed_test_data.py --concurrent --lists 3

    # Hammer SQLite with concurrent writers
    python scripts/seed_test_data.py --concurrent --workers 4 --min 50_000 --max 200_000

    # Add videos to existing lists instead of creating new ones
    python scripts/seed_test_data.py --concurrent --use-existing

"""

from __future__ import annotations

import argparse
import random
import string
import sys
import threading
import time
import uuid
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta

# Ensure the application package is importable
sys.path.insert(0, "/app")

from app.extensions import SessionLocal  # noqa: E402
from app.models import Profile, Video, VideoList  # noqa: E402
from app.models.settings import Settings  # noqa: E402
from app.task_queue import SETTING_SYNC_PAUSED  # noqa: E402

DEFAULT_WORKERS = 4
DEFAULT_LIST_COUNT = 1

DEFAULT_MIN_VIDEOS = 50_000
DEFAULT_MAX_VIDEOS = 5_000_000

DEFAULT_BATCH_MIN = 1
DEFAULT_BATCH_MAX = 4_000

TEST_PROFILE_NAME = "Test Profile"

progress_lock = threading.Lock()
progress: dict[int, ProgressState] = {}


@dataclass(slots=True)
class ProgressState:
    name: str
    current: int
    total: int
    status: str = "running"

    @property
    def percent(self) -> float:
        return (self.current / self.total) * 100 if self.total else 0.0


def random_string(length: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def random_date(start_year: int = 2015) -> datetime:
    start = datetime(start_year, 1, 1)
    delta_days = (datetime.now() - start).days
    return start + timedelta(days=random.randint(0, delta_days))


def build_video(list_id: int, index: int) -> Video:
    """Create a single Video instance with dummy metadata."""
    return Video(
        video_id=f"vid_{uuid.uuid4().hex}",
        title=f"Test Video {index} – {random_string(16)}",
        url=random_string(11),
        duration=random.randint(60, 7_200),
        upload_date=random_date(),
        thumbnail="https://i.ytimg.com/vi/WzDmoTydaEk/maxresdefault.jpg",
        description=f"Synthetic test description {random_string(200)}",
        extractor="youtube",
        media_type="video",
        labels={
            "format": random.choice(["mp4", "webm", "mkv"]),
            "resolution": random.choice(["480p", "720p", "1080p", "4K"]),
            "acodec": random.choice(["aac", "opus", "mp3"]),
        },
        list_id=list_id,
        downloaded=random.random() < 0.1,
    )


def batched(
    iterable: Iterable[int], min_size: int, max_size: int
) -> Iterable[list[int]]:
    """Yield indices in randomly sized batches."""
    items = list(iterable)
    i = 0
    while i < len(items):
        size = random.randint(min_size, max_size)
        yield items[i : i + size]
        i += size


def populate_existing_list(
    list_id: int,
    list_name: str,
    video_count: int,
    batch_min: int,
    batch_max: int,
) -> dict:
    """Populate an existing list with videos."""
    started = time.perf_counter()

    with SessionLocal() as db:
        start_index = (
            db.query(Video.id)
            .filter(Video.list_id == list_id)
            .order_by(Video.id.desc())
            .limit(1)
            .scalar()
            or 0
        ) + 1

        with progress_lock:
            progress[list_id] = ProgressState(list_name, 0, video_count)

        for batch in batched(range(video_count), batch_min, batch_max):
            videos = [build_video(list_id, start_index + i) for i in batch]
            db.bulk_save_objects(videos)
            db.commit()

            with progress_lock:
                state = progress[list_id]
                state.current += len(batch)

    elapsed = time.perf_counter() - started
    return _result(list_id, list_name, video_count, elapsed)


def create_and_populate_list(
    profile_id: int,
    index: int,
    video_count: int,
    batch_min: int,
    batch_max: int,
) -> dict:
    """Create a new list."""
    started = time.perf_counter()

    with SessionLocal() as db:
        video_list = VideoList(
            name=f"Test Channel {index + 1}",
            url=f"{random_string(24)}_{index}",
            list_type="channel",
            profile_id=profile_id,
            enabled=False,
            auto_download=False,
            extractor="youtube",
        )
        db.add(video_list)
        db.commit()
        db.refresh(video_list)

        with progress_lock:
            progress[video_list.id] = ProgressState(
                video_list.name, 0, video_count, status="created"
            )

        for batch in batched(range(video_count), batch_min, batch_max):
            videos = [build_video(video_list.id, i) for i in batch]
            db.bulk_save_objects(videos)
            db.commit()

            with progress_lock:
                state = progress[video_list.id]
                state.current += len(batch)
                state.status = "populating"

    elapsed = time.perf_counter() - started
    return _result(video_list.id, video_list.name, video_count, elapsed)


def _result(list_id: int, name: str, count: int, elapsed: float) -> dict:
    return {
        "list_id": list_id,
        "list_name": name,
        "videos_added": count,
        "elapsed_seconds": elapsed,
        "videos_per_second": count / elapsed if elapsed else 0.0,
    }


def print_progress() -> None:
    with progress_lock:
        if not progress:
            return

        print("\n--- Progress ---")
        for state in progress.values():
            print(
                f"{state.name}: "
                f"{state.current:,}/{state.total:,} "
                f"({state.percent:5.1f}%) "
                f"[{state.status}]"
            )


def concurrent_populate(
    *,
    workers: int,
    list_count: int,
    min_videos: int,
    max_videos: int,
    use_existing: bool,
    batch_min: int,
    batch_max: int,
) -> None:
    """Run concurrent writers against SQLite."""

    print(
        f"Concurrent mode: {workers} workers, "
        f"{min_videos:,}–{max_videos:,} videos per list"
    )

    with SessionLocal() as db:
        Settings.set_bool(db, SETTING_SYNC_PAUSED, True)

        profile = db.query(Profile).filter_by(
            name=TEST_PROFILE_NAME
        ).first() or Profile(name=TEST_PROFILE_NAME)
        db.add(profile)
        db.commit()
        db.refresh(profile)

        existing_lists = db.query(VideoList).all()

    jobs = []

    if use_existing and existing_lists:
        for lst in existing_lists:
            jobs.append(
                lambda lst=lst: populate_existing_list(
                    lst.id,
                    lst.name,
                    random.randint(min_videos, max_videos),
                    batch_min,
                    batch_max,
                )
            )
    else:
        for i in range(list_count):
            jobs.append(
                lambda i=i: create_and_populate_list(
                    profile.id,
                    i,
                    random.randint(min_videos, max_videos),
                    batch_min,
                    batch_max,
                )
            )

    stop = threading.Event()

    def monitor() -> None:
        while not stop.wait(5):
            print_progress()

    threading.Thread(target=monitor, daemon=True).start()

    started = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(job) for job in jobs]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{result['list_name']}: "
                f"{result['videos_added']:,} videos in "
                f"{result['elapsed_seconds']:.1f}s"
            )

    stop.set()

    elapsed = time.perf_counter() - started
    total = sum(r["videos_added"] for r in results)

    print("\n" + "=" * 60)
    print(f"Lists completed : {len(results)}")
    print(f"Total videos   : {total:,}")
    print(f"Elapsed time   : {elapsed:.1f}s")
    print(f"Overall rate   : {total / elapsed:,.0f} videos/s")
    print("Sync workers remain paused.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the database with dummy test data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--concurrent", action="store_true")
    parser.add_argument("--use-existing", action="store_true")

    parser.add_argument("--add", type=int, metavar="COUNT")
    parser.add_argument("--list-id", type=int)

    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--lists", type=int, default=DEFAULT_LIST_COUNT)

    parser.add_argument(
        "--min", dest="min_videos", type=int, default=DEFAULT_MIN_VIDEOS
    )
    parser.add_argument(
        "--max", dest="max_videos", type=int, default=DEFAULT_MAX_VIDEOS
    )

    args = parser.parse_args()

    if args.list_id and not args.add:
        parser.error("--list-id requires --add")

    if args.concurrent:
        concurrent_populate(
            workers=args.workers,
            list_count=args.lists,
            min_videos=args.min_videos,
            max_videos=args.max_videos,
            use_existing=args.use_existing,
            batch_min=DEFAULT_BATCH_MIN,
            batch_max=DEFAULT_BATCH_MAX,
        )


if __name__ == "__main__":
    main()
