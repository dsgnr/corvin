"""
Shared constants for the application.
"""

# Resolution name to height mapping (0 = audio only)
RESOLUTION_MAP = {
    0: "Audio Only",
    4320: "8K",
    2160: "4K",
    1440: "2K",
    1080: "Full HD",
    720: "HD",
    480: "SD",
    360: "360p",
}

# Video codec options (yt-dlp format_sort values)
VIDEO_CODECS = ["av01", "vp9.2", "vp9", "h265", "h264"]

# Audio codec options (yt-dlp format_sort values)
AUDIO_CODECS = ["flac", "alac", "wav", "opus", "vorbis", "aac", "mp4a", "mp3"]
