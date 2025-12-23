# Corvin

Corvin is a self-hosted media ingestion and archiving tool. It monitors channels and playlists, keeps them in sync, and downloads new videos using flexible, configurable profiles.

While YouTube is my most common use case, it should work with anything supported by yt-dlp.

The project is API first by design. The included web interface is optional, making it easy to automate workflows or build a custom frontend.

## Features

- Monitor channels and playlists from YouTube and other yt-dlp supported platforms
- Optimised indexing approach using threads.
- Automatic syncing on configurable schedules (daily, weekly, monthly)
- Download profiles with granular control over format, quality, and post-processing
- SponsorBlock integration to skip or mark sponsored segments
- Subtitle downloading and embedding
- Metadata and thumbnail embedding
- Background task queue with concurrent workers
- Web interface for managing lists, profiles, and monitoring tasks

## Installation

> [!NOTE]
> Example docker compose file can be found at [docker-compose.yml](docker-compose.yml)
> **Be sure to define the volume paths to suit you!**

```
$ docker compose up
```

The front-end will be running at [http://0.0.0.0:3000](http://0.0.0.0:3000) and the API will be running at [http://0.0.0.0:5000](http://0.0.0.0:5000).

## Configuration

### Directory Structure

```
./data/       # SQLite database
./downloads/  # Downloaded media files
```

Both directories are mounted as volumes and persist between container restarts.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE` | `http://localhost:5000/api` | API URL for the frontend |

### Worker Configuration

The backend supports configurable worker pools in `app/__init__.py`:

- `MAX_SYNC_WORKERS`: Concurrent list sync operations (default: 2)
- `MAX_DOWNLOAD_WORKERS`: Concurrent video downloads (default: 3)

## API

The REST API is the primary interface. All endpoints are under `/api/`:

| Endpoint | Description |
|----------|-------------|
| `/api/profiles` | Manage download profiles |
| `/api/lists` | Manage video lists (channels/playlists) |
| `/api/videos` | View and manage discovered videos |
| `/api/tasks` | View task queue and status |
| `/api/history` | View activity history |

Standard REST conventions apply. `GET`, `POST`, `PUT`, `DELETE` where appropriate.

## Download Profiles

Profiles control how videos are downloaded and processed. Each profile supports:

- **Output format**: mp4, webm, mp3, etc.
- **Output template**: Customise file naming and folder structure using standard yt-dlp template syntax
- **Metadata embedding**: Include video metadata in the file
- **Thumbnail embedding**: Embed thumbnails as cover art
- **Subtitles**: Download, embed, or fetch auto-generated subtitles
- **Audio track language**: Prefer specific audio languages
- **SponsorBlock**: Skip or mark sponsored segments, intros, outros, etc.
- **Extra arguments**: Pass additional yt-dlp options as JSON

### Default Output Template

```
%(uploader)s/s%(upload_date>%Y)se%(upload_date>%m%d)s - %(title)s.%(ext)s
```

This organises downloads by uploader, with files named by season (year) and episode (date).

## Video Lists

Lists represent channels or playlists to monitor. Each list is assigned a download profile and supports:

- **Sync frequency**: How often to check for new videos
- **From date**: Only sync videos uploaded after this date
- **Auto-download**: Automatically queue new videos for download. This can be disabled for an "index only" mode, with the ability to manually download specific videos.
- **Exclude shorts**: Skip YouTube Shorts (profile setting)

## Development

For local development with live reloading:

```bash
docker compose -f docker-compose-dev.yml up
```

This mounts source directories and enables debug mode.

### Code Quality

The project uses ruff for Python linting and formatting:

```bash
cd backend
poetry run ruff check .
poetry run ruff format .
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`.

## Architecture

- **Backend**: Flask with SQLAlchemy, APScheduler for periodic tasks, yt-dlp for media extraction
- **Frontend**: Next.js with React, Tailwind CSS
- **Database**: SQLite (stored in `./data/corvin.db`)
- **Task Queue**: Custom in-memory queue with persistent task state

## Contributing

I'm thrilled that you’re interested in contributing to this project! Here’s how you can get involved:

### How to Contribute

1. **Submit Issues**:

   - If you encounter any bugs or have suggestions for improvements, please submit an issue on our [GitHub Issues](https://github.com/dsgnr/corvin/issues) page.
   - Provide as much detail as possible, including steps to reproduce and screenshots if applicable.

2. **Propose Features**:

   - Have a great idea for a new feature? Open a feature request issue in the same [GitHub Issues](https://github.com/dsgnr/corvin/issues) page.
   - Describe the feature in detail and explain how it will benefit the project.

3. **Submit Pull Requests**:
   - Fork the repository and create a new branch for your changes.
   - Make your modifications and test thoroughly.
   - Open a pull request against the `devel` branch of the original repository. Include a clear description of your changes and any relevant context.


## Author

- Website: https://danielhand.io
- Github: [@dsgnr](https://github.com/dsgnr)

## License

See the [LICENSE](LICENSE) file for more details on terms and conditions.