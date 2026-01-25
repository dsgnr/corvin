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

# Video codecs: value -> display label (yt-dlp format_sort values)
VIDEO_CODECS = {
    "av01": "AV1",
    "h264": "H.264/AVC",
    "h265": "H.265/HEVC",
    "vp9": "VP9",
    "vp9.2": "VP9.2 (HDR)",
}

# Audio codecs: value -> display label (yt-dlp format_sort values)
AUDIO_CODECS = {
    "aac": "AAC",
    "alac": "ALAC",
    "flac": "FLAC",
    "mp3": "MP3",
    "mp4a": "MP4A",
    "opus": "Opus",
    "vorbis": "Vorbis",
    "wav": "WAV",
}

# SponsorBlock behaviour options
SPONSORBLOCK_DISABLED = "disabled"
SPONSORBLOCK_DELETE = "delete"
SPONSORBLOCK_MARK_CHAPTER = "mark_chapter"
SPONSORBLOCK_BEHAVIOURS = [
    SPONSORBLOCK_DISABLED,
    SPONSORBLOCK_DELETE,
    SPONSORBLOCK_MARK_CHAPTER,
]

# SponsorBlock categories: value -> display label
SPONSORBLOCK_CATEGORIES = {
    "sponsor": "Sponsor",
    "intro": "Intro/Intermission",
    "outro": "Outro/Credits",
    "selfpromo": "Unpaid/Self Promotion",
    "preview": "Preview/Recap",
    "interaction": "Interaction Reminder (Subscribe)",
    "music_offtopic": "Music: Non-Music Section",
    "filler": "Tangents/Jokes",
}

# Default output template for profiles
DEFAULT_OUTPUT_TEMPLATE = (
    "%(uploader)s/Season %(upload_date>%Y)s/"
    "s%(upload_date>%Y)se%(upload_date>%m%d)s - %(title)s.%(ext)s"
)
