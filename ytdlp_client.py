import re

YOUTUBE_PATTERNS = [
    r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})",
    r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
]


def extract_video_id(video_input: str) -> str:
    """Extract video ID from various YouTube URL formats or plain ID."""
    video_input = video_input.strip()
    if len(video_input) == 11 and "/" not in video_input and "." not in video_input:
        return video_input
    for pattern in YOUTUBE_PATTERNS:
        match = re.search(pattern, video_input)
        if match:
            return match.group(1)
    return video_input
