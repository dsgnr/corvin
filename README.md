# Corvin

A self-hosted media archiver that monitors subscribed channels and playlists, keeps them in sync, and downloads new videos using configurable profiles.

Works with anything yt-dlp supports, though YouTube is the primary use case.

The project is API-first by design. The web interface is optional, making it straightforward to automate workflows or build a custom frontend.

## Features

- Monitor channels and playlists from YouTube and other yt-dlp supported platforms
- Optimised indexing approach
- Automatic syncing on configurable schedules (daily, weekly, monthly)
- Download profiles with control over format, quality, and post-processing
- SponsorBlock integration to skip or mark sponsored segments
- Subtitle downloading and embedding
- Metadata and thumbnail embedding
- Background task queue with concurrent workers
- Real-time download progress via SSE
- Web interface for managing lists, profiles, and monitoring tasks
- OpenAPI documentation with Scalar UI

## Installation

> [!NOTE]
> Example docker compose file can be found at [docker-compose.yml](docker-compose.yml)
> **Be sure to define the volume paths to suit you!**

```bash
docker compose up -d
```

Once running:
- Web UI: http://localhost
- API: http://localhost:5000
- API Docs: http://localhost:5000/api/docs

## Configuration

### Directory Structure

```
./corvin_data/    # SQLite database
./downloads/      # Downloaded media files
```

Both directories are mounted as volumes and persist between container restarts.

### Environment Variables

**Backend:**

| Variable | Default | Description |
|----------|---------|-------------|
| `TZ` | `UTC` | Container timezone |
| `MAX_SYNC_WORKERS` | `2` | Concurrent sync operations |
| `MAX_DOWNLOAD_WORKERS` | `2` | Concurrent downloads |

**Frontend:**

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://backend:5000` | Backend API URL (Docker internal network) |

## API

The REST API is the primary interface. All endpoints are under `/api/`:

| Endpoint | Description |
|----------|-------------|
| `/api/profiles` | Manage download profiles |
| `/api/lists` | Manage video lists (channels/playlists) |
| `/api/videos` | View and manage discovered videos |
| `/api/tasks` | View task queue and status |
| `/api/history` | View activity history |
| `/api/progress` | Real-time download progress (SSE) |
| `/api/docs` | Interactive API documentation (Scalar) |

Standard REST conventions apply. `GET`, `POST`, `PUT`, `DELETE` where appropriate.

## Download Profiles

Profiles control how videos are downloaded and processed:

- **Output format** — mp4, webm, mp3, etc.
- **Output template** — file naming using yt-dlp template syntax
- **Metadata embedding** — include video metadata in the file
- **Thumbnail embedding** — embed thumbnails as cover art
- **Subtitles** — download, embed, or fetch auto-generated
- **Audio language** — prefer specific audio tracks
- **SponsorBlock** — skip or mark sponsors, intros, outros
- **Extra arguments** — additional yt-dlp options as JSON

Default output template:
```
%(uploader)s/s%(upload_date>%Y)se%(upload_date>%m%d)s - %(title)s.%(ext)s
```

This organises downloads by uploader, with files named by season (year) and episode (date).

## Video Lists

Lists represent channels or playlists to monitor:

- **Sync frequency** — how often to check for new videos
- **From date** — only sync videos uploaded after this date
- **Auto-download** — automatically queue new videos for download
- **Exclude shorts** — skip YouTube Shorts

Disable auto-download for an "index only" mode, then manually download specific videos as needed.

## Development

For local development with live reloading:

```bash
docker compose -f docker-compose-dev.yml up
```

The frontend runs on port 3000 in development mode.

### Local Setup

**Backend:**
```bash
cd backend
uv sync
uv run python run.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Code Quality

The project uses ruff for Python linting and formatting:

```bash
cd backend
uv run ruff check .
uv run ruff format .
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`.

### Running Tests

```bash
cd backend
uv run pytest
```

## Architecture

- **Backend**: Flask, SQLAlchemy, APScheduler for periodic tasks, yt-dlp for media extraction
- **Frontend**: Next.js with React, Tailwind CSS
- **Database**: SQLite (stored in `./corvin_data/corvin.db`)
- **Task Queue**: Custom in-memory queue with persistent task state
- **Scheduler**: Syncs every 30 minutes, downloads every 5 minutes

## Requirements

- Docker and Docker Compose
- Python 3.13+ (for local development)
- Node.js 20+ (for local frontend development)

## Contributing

I'm thrilled that you're interested in contributing to this project! Here's how you can get involved:

### How to Contribute

1. **Submit Issues**: If you encounter any bugs or have suggestions for improvements, please submit an issue on our [GitHub Issues](https://github.com/dsgnr/corvin/issues) page.

2. **Propose Features**: Have a great idea for a new feature? Open a feature request issue in the same [GitHub Issues](https://github.com/dsgnr/corvin/issues) page.

3. **Submit Pull Requests**: Fork the repository and create a new branch for your changes. Make your modifications and test thoroughly. Open a pull request against the `devel` branch of the original repository.

## Author

- Website: https://danielhand.io
- Github: [@dsgnr](https://github.com/dsgnr)

## License

See the [LICENSE](LICENSE) file for more details on terms and conditions.
