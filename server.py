import logging
import signal
import sys

from fastmcp import FastMCP

from tools import transcript as t_transcript

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


def _signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, shutting down gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    logger.info("Starting YouTube Transcript MCP Server...")
    mcp.run(transport="http", host="0.0.0.0", port=8000, json_response=True)
