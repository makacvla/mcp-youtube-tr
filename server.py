import json
import logging
from mcp.server.fastmcp import FastMCP
from youtube_transcript_api import YouTubeTranscriptApi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("youtube-transcript-mcp")

mcp = FastMCP(
    "YouTube Transcript",
    description="MCP server for fetching YouTube video transcripts",
    stateless_http=True,
    json_response=True,
)

def extract_video_id(video_input: str) -> str:
    """Extract video ID from various YouTube URL formats or plain ID."""
    video_input = video_input.strip()

    # Already a plain ID (11 chars, no slashes)
    if len(video_input) == 11 and "/" not in video_input and "." not in video_input:
        return video_input

    # Handle various URL formats
    import re
    patterns = [
        r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, video_input)
        if match:
            return match.group(1)

    # Fallback: return as-is (might be an ID of different length)
    return video_input


@mcp.tool()
def get_transcript(
    video: str,
    languages: str = "en,ru",
    timestamps: bool = True,
) -> str:
    """Fetch transcript (subtitles) for a YouTube video without watching it.

    Args:
        video: YouTube video ID or full URL
            (e.g. "dQw4w9WgXcQ" or "https://youtube.com/shorts/dQw4w9WgXcQ")
        languages: Comma-separated language codes in priority order (default: "en,ru")
        timestamps: Include timestamps in output (default: true)

    Returns:
        Full transcript text with optional timestamps.
        Also includes metadata: language, whether auto-generated, video ID.
    """
    video_id = extract_video_id(video)
    lang_list = [l.strip() for l in languages.split(",") if l.strip()]

    api = YouTubeTranscriptApi()

    # List available transcripts
    available = api.list(video_id)
    available_info = []
    for t in available:
        available_info.append({
            "language": t.language,
            "language_code": t.language_code,
            "is_generated": t.is_generated,
        })

    # Try to fetch in preferred language order
    transcript = None
    used_lang = None
    errors = []

    for lang in lang_list:
        try:
            transcript = api.fetch(video_id, languages=[lang])
            used_lang = lang
            break
        except Exception as e:
            errors.append(f"{lang}: {e}")

    # Fallback: fetch default transcript
    if transcript is None:
        try:
            transcript = api.fetch(video_id)
            used_lang = "default"
        except Exception as e:
            return json.dumps({
                "error": f"Could not fetch transcript: {e}",
                "tried_languages": lang_list,
                "available_transcripts": available_info,
                "video_id": video_id,
            }, ensure_ascii=False, indent=2)

    # Format output
    lines = []
    for entry in transcript:
        if timestamps:
            minutes = int(entry.start // 60)
            seconds = int(entry.start % 60)
            lines.append(f"[{minutes:02d}:{seconds:02d}] {entry.text}")
        else:
            lines.append(entry.text)

    text = "\n".join(lines)

    result = {
        "video_id": video_id,
        "language": used_lang,
        "available_transcripts": available_info,
        "transcript": text,
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
