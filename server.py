import logging
import signal
import sys

from fastmcp import FastMCP

from tools import transcript as t_transcript
from tools import video as t_video
from tools import discovery as t_discovery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("youtube-transcript-mcp")

mcp = FastMCP("YouTube Transcript", stateless_http=True)


@mcp.tool()
def get_transcript(video: str, languages: str = "en,ru", timestamps: bool = True) -> str:
    """Fetch transcript (subtitles) for a YouTube video.

    Args:
        video: YouTube video ID or full URL
        languages: Comma-separated language codes in priority order (default: "en,ru")
        timestamps: Include [MM:SS] timestamps in output (default: true)
    """
    return t_transcript.get_transcript(video, languages, timestamps)


@mcp.tool()
def list_available_transcripts(video: str) -> str:
    """List all available transcript tracks for a YouTube video without fetching content.

    Args:
        video: YouTube video ID or full URL
    """
    return t_transcript.list_available_transcripts(video)


@mcp.tool()
def get_transcript_chunk(
    video: str,
    from_sec: int,
    to_sec: int,
    languages: str = "en,ru",
    timestamps: bool = True,
) -> str:
    """Fetch transcript segment between [from_sec, to_sec).

    Args:
        video: YouTube video ID or full URL
        from_sec: Start time in seconds (inclusive)
        to_sec: End time in seconds (exclusive)
        languages: Comma-separated language codes (default: "en,ru")
        timestamps: Include [MM:SS] timestamps (default: true)
    """
    return t_transcript.get_transcript_chunk(video, from_sec, to_sec, languages, timestamps)


@mcp.tool()
def search_in_transcript(
    video: str,
    query: str,
    languages: str = "en,ru",
    context_chars: int = 50,
) -> str:
    """Search for a substring within a video's transcript; returns timestamped matches.

    Args:
        video: YouTube video ID or full URL
        query: Text to search for (case-insensitive)
        languages: Comma-separated language codes (default: "en,ru")
        context_chars: Characters of context to include around each match (default: 50)
    """
    return t_transcript.search_in_transcript(video, query, languages, context_chars)


@mcp.tool()
def get_video_info(video: str) -> str:
    """Fetch metadata about a YouTube video without watching it.

    Args:
        video: YouTube video ID or full URL
    """
    return t_video.get_video_info(video)


@mcp.tool()
def get_video_chapters(video: str) -> str:
    """Fetch chapter markers (title + start/end seconds) for a YouTube video.

    Args:
        video: YouTube video ID or full URL
    """
    return t_video.get_video_chapters(video)


@mcp.tool()
def get_thumbnail_url(video: str, quality: str = "max") -> str:
    """Get a thumbnail URL for a YouTube video at the requested quality.

    Args:
        video: YouTube video ID or full URL
        quality: One of "max", "high", "medium", "default" (default: "max")
    """
    return t_video.get_thumbnail_url(video, quality)


@mcp.tool()
def search_videos(query: str, max_results: int = 10) -> str:
    """Search YouTube and return the top N videos with metadata.

    Args:
        query: Search query string
        max_results: Number of results, 1 to 50 (default: 10)
    """
    return t_discovery.search_videos(query, max_results)


@mcp.tool()
def get_channel_info(channel: str) -> str:
    """Fetch metadata for a YouTube channel (handle, URL, or UC… ID).

    Args:
        channel: @handle, full channel URL, or UC… channel ID
    """
    return t_discovery.get_channel_info(channel)


@mcp.tool()
def list_channel_videos(channel: str, max_results: int = 20) -> str:
    """List recent videos from a YouTube channel.

    Args:
        channel: @handle, full channel URL, or UC… channel ID
        max_results: Number of videos to return, 1 to 100 (default: 20)
    """
    return t_discovery.list_channel_videos(channel, max_results)


@mcp.tool()
def get_playlist_videos(playlist: str, max_results: int = 50) -> str:
    """List videos in a YouTube playlist.

    Args:
        playlist: Playlist ID (PL…) or full playlist URL
        max_results: Number of videos to return, 1 to 200 (default: 50)
    """
    return t_discovery.get_playlist_videos(playlist, max_results)


def _signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, shutting down gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    logger.info("Starting YouTube Transcript MCP Server...")
    mcp.run(transport="http", host="0.0.0.0", port=8000, json_response=True)
