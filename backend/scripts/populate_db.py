#!/usr/bin/env python3
"""Development helper script to populate the database via the API."""

import argparse
import sys

import requests

DEFAULT_BASE_URL = "http://localhost:5000/api"

PROFILE = {
    "name": "Default HD Profile",
    "output_format": "mp4",
    "embed_metadata": True,
    "embed_thumbnail": True,
    "exclude_shorts": True,
    "download_subtitles": True,
    "embed_subtitles": True,
    "auto_generated_subtitles": True,
}

LISTS = [
    ("Jeff Geerling", "https://www.youtube.com/@JeffGeerling", True),
    ("ServeTheHome", "https://www.youtube.com/@ServeTheHomeVideo", False),
]


def get_or_create_profile(session: requests.Session, base_url: str) -> int | None:
    """Get existing or create new profile."""
    resp = session.post(f"{base_url}/profiles/", json=PROFILE, timeout=10)
    if resp.status_code == 201:
        p = resp.json()
        print(f"Created profile: {p['name']} (ID: {p['id']})")
        return p["id"]
    if resp.status_code == 409:
        for p in session.get(f"{base_url}/profiles/", timeout=10).json():
            if p["name"] == PROFILE["name"]:
                print(f"Using existing profile: {p['name']} (ID: {p['id']})")
                return p["id"]
    print(f"Profile error: {resp.status_code} - {resp.text}")
    return None


def create_list(
    session: requests.Session,
    base_url: str,
    profile_id: int,
    name: str,
    url: str,
    auto_download: bool,
) -> None:
    """Create a video list."""
    resp = session.post(
        f"{base_url}/lists/",
        json={
            "name": name,
            "url": url,
            "profile_id": profile_id,
            "auto_download": auto_download,
        },
        timeout=30,
    )
    status = "enabled" if auto_download else "disabled"
    if resp.status_code == 201:
        print(f"Created: {name} (auto_download: {status})")
    elif resp.status_code == 409:
        print(f"Exists: {name}")
    else:
        print(f"Failed: {name} - {resp.status_code}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate database with sample data")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    session = requests.Session()
    try:
        profile_id = get_or_create_profile(session, args.base_url)
        if not profile_id:
            sys.exit(1)

        for name, url, auto_dl in LISTS:
            create_list(session, args.base_url, profile_id, name, url, auto_dl)

        print("\nDone!")
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to {args.base_url}")
        sys.exit(1)


if __name__ == "__main__":
    main()
