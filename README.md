# Corvin

A self-hosted media archiver that monitors subscribed channels and playlists, keeps them in sync, and downloads new videos using configurable profiles.

Works with anything yt-dlp supports, though YouTube is the primary use case.

The project is API-first by design. The web interface is optional, making it straightforward to automate workflows or build a custom frontend.

## Features

- Monitor channels and playlists from YouTube and other yt-dlp supported platforms
- Optimised indexing approach
- Automatic syncing on configurable schedules (daily, weekly, monthly)
- Download profiles with control over format, quality, and post-processing
- Download scheduling to restrict downloads to specific time windows
- SponsorBlock integration to skip or mark sponsored segments
- Subtitle downloading and embedding
- Metadata and thumbnail embedding
- Background task queue with concurrent workers
- Real-time download progress via SSE
- Web interface for managing lists, profiles, and monitoring tasks
- OpenAPI documentation with Scalar UI
- SQLite or PostgreSQL backends

## Installation

> [!NOTE]
> Example docker compose file can be found at [docker-compose.yml](docker-compose.yml)
> **Be sure to define the volume paths to suit you!**

```bash
docker compose up -d
```

Once running:
- Web UI: http://localhost

The API is proxied through the frontend, so you only need to expose port 80.

### Using PostgreSQL

For PostgreSQL instead of SQLite, use the PostgreSQL compose file:

```bash
# Copy and configure the example env file
cp .env.postgres.example .env

# Edit .env and set POSTGRES_PASSWORD
nano .env

# Start with PostgreSQL
docker compose -f docker-compose-postgres.yml up -d
```

See [docker-compose-postgres.yml](docker-compose-postgres.yml) for the full configuration.

## Configuration

### Directory Structure

```
./corvin_data/    # SQLite database (when using SQLite)
./downloads/      # Downloaded media files
```

Both directories are mounted as volumes and persist between container restarts.

### Network Share Storage

If you need to store the SQLite database on a network share (NFS, SMB, etc.), enable network share compatibility mode:

```yaml
environment:
  - SQLITE_NETWORK_SHARE=true
```

This switches SQLite from WAL mode to rollback journal mode, which works reliably over network filesystems. Trade-offs:
- Slower write performance
- Exclusive locking (one writer at a time)

I probably wouldn't recommend this, but it's there if you want it.

### Environment Variables

**Backend:**

| Variable | Default | Description |
|----------|---------|-------------|
| `TZ` | `UTC` | Container timezone |
| `MAX_SYNC_WORKERS` | `2` | Concurrent sync operations |
| `MAX_DOWNLOAD_WORKERS` | `2` | Concurrent downloads |
| `POSTGRES_HOST` | | PostgreSQL host (enables PostgreSQL mode) |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `corvin` | PostgreSQL username |
| `POSTGRES_PASSWORD` | | PostgreSQL password (required when using PostgreSQL) |
| `POSTGRES_DB` | `corvin` | PostgreSQL database name |
| `SQLITE_NETWORK_SHARE` | `false` | Enable network share compatibility mode for SQLite |
| `NOTIFICATION_PLEX_TOKEN` | | Plex authentication token |
| `NOTIFICATION_JELLYFIN_API_KEY` | | Jellyfin/Emby API key |
| `NOTIFICATION_SLACK_WEBHOOK_URL` | | Slack webhook URL |
| `NOTIFICATION_DISCORD_WEBHOOK_URL` | | Discord webhook URL |
| `NOTIFICATION_NTFY_ACCESS_TOKEN` | | ntfy access token |
| `NOTIFICATION_GOTIFY_APP_TOKEN` | | Gotify application token |

**Frontend:**

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://backend:5000` | Backend API URL. Only needed if the backend service name differs from `backend` (e.g., Kubernetes) |

## API

The REST API is the primary interface. All endpoints are under `/api/`:

| Endpoint | Description |
|----------|-------------|
| `/api/profiles` | Manage download profiles |
| `/api/lists` | Manage video lists (channels/playlists) |
| `/api/videos` | View and manage discovered videos |
| `/api/tasks` | View task queue and status |
| `/api/history` | View activity history |
| `/api/schedules` | Manage download time windows |
| `/api/settings` | Manage application settings |
| `/api/progress` | Real-time download progress (SSE) |
| `/api/docs` | Interactive API documentation (Scalar) |
| `/health` | Health check endpoint |

Standard REST conventions apply. `GET`, `POST`, `PUT`, `DELETE` where appropriate.

The API is accessible via the frontend proxy at `http://localhost/api/` or directly at `http://localhost:5000/api/` if you expose the backend port.

## Download Profiles

Profiles control how videos are downloaded and processed:

- **Preferred resolution** — target video quality (4K, 1080p, 720p, etc.) or audio-only mode
- **Video codec** — prefer specific codecs (AV1, VP9, H.264, etc.)
- **Audio codec** — prefer specific audio codecs (Opus, AAC, etc.)
- **Output format** — container format (mp4, mkv, webm, etc.)
- **Output template** — file naming using yt-dlp template syntax
- **Metadata embedding** — include video metadata in the file
- **Thumbnail embedding** — embed thumbnails as cover art
- **Subtitles** — download, embed, or fetch auto-generated
- **Audio language** — prefer specific audio tracks
- **SponsorBlock** — skip or mark sponsors, intros, outros
- **Content filters** — include or exclude Shorts and live streams
- **Windows-compatible filenames** — force filenames to be Windows-compatible
- **Restrict filenames** — limit filenames to ASCII characters, avoiding `&` and spaces
- **Extra arguments** — additional yt-dlp options as JSON

Default output template:
```
%(uploader)s/Season %(upload_date>%Y)s/s%(upload_date>%Y)se%(upload_date>%m%d)s - %(title)s.%(ext)s
```
Renders as:
```
channel_name/Season YYYY/s20YYeMMDD video title.ext
```

This organises downloads by uploader, then season (year), with files named by season (year) and episode (date).

## Video Lists

Lists represent channels or playlists to monitor:

- **Sync frequency** — how often to check for new videos
- **From date** — only sync videos uploaded after this date
- **Auto-download** — automatically queue new videos for download
- **Regex matching** — exclude videos from automatically downloading based on regex.

Disable auto-download for an "index only" mode, then manually download specific videos as needed.

## Download Schedules

Schedules allow you to restrict downloads to specific time windows:

- **Days of week** — which days the schedule is active
- **Start/end time** — the time window when downloads are permitted
- **Enable/disable** — toggle schedules without deleting them

When no schedules are defined or enabled, downloads run at any time. When schedules are active, downloads only proceed during the permitted windows.

## Data Retention

Corvin automatically cleans up old completed tasks and history entries to prevent database bloat:

- **Retention period** — number of days to keep completed/failed tasks and history (default: 90 days)
- **Automatic cleanup** — runs daily at 3 AM
- **Disable cleanup** — set retention to 0 to keep all data indefinitely
- **Database vacuum** — manually reclaim disk space after cleanup (SQLite only)

Configure data retention in **Settings** > **Data Retention**. Only completed, failed, and cancelled tasks are pruned; pending and running tasks are always preserved.

For SQLite databases, use the "Run VACUUM" button to compact the database file and reclaim disk space after deleting large amounts of data. PostgreSQL handles this automatically.

## yt-dlp Updates

Corvin automatically keeps yt-dlp up to date to ensure compatibility with the latest site changes:

- **Automatic updates** — yt-dlp is updated to the latest nightly build on every container start and daily at 4 AM
- **Manual updates** — trigger an update anytime (if one is available) from **Settings** > **About**
- **Version info** — view current and latest available versions in the settings UI

This ensures you always have the latest extractors and bug fixes without manual intervention.

## Notifications

Corvin supports pluggable notification integrations to alert external services when events occur:

### Supported Integrations

| Integration | Description |
|-------------|-------------|
| Plex | Trigger library scans when new media is downloaded |
| Jellyfin / Emby | Trigger library scans when new media is downloaded |
| Slack | Send messages via incoming webhooks |
| Discord | Send messages via webhooks with rich embeds |
| ntfy | Send push notifications via ntfy.sh or self-hosted |
| Gotify | Send push notifications via Gotify server |

### Supported Events

| Event | Description |
|-------|-------------|
| Download Completed | Triggered when a video finishes downloading |
| Video Discovered | Triggered when new videos are found during sync |
| Sync Completed | Triggered when a list sync completes |

Configure notifications in **Settings** > **Notifications**. Each integration can be enabled independently with its own event triggers.

## Development

For local development with live reloading:

```bash
docker compose -f docker-compose-dev.yml up
```

For development with PostgreSQL:

```bash
docker compose -f docker-compose-postgres-dev.yml up
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

Frontend uses ESLint and Prettier:

```bash
cd frontend
npm run lint
npm run format
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`.

### Running Tests

```bash
cd backend
uv run pytest
```

## Architecture

- **Backend**: FastAPI, SQLAlchemy, APScheduler for periodic tasks, yt-dlp for media extraction
- **Frontend**: Next.js 16 with React 19, Tailwind CSS 4
- **Database**: SQLite (default) or PostgreSQL
- **Task Queue**: Custom in-memory queue with persistent task state

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

## Licence

See the [LICENCE](LICENSE) file for more details on terms and conditions.
