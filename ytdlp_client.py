import os
import re
import time
from collections import OrderedDict
from functools import wraps
from yt_dlp import YoutubeDL

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


MAX_CACHE_ENTRIES = 500
_cache: "OrderedDict[tuple, tuple[float, object]]" = OrderedDict()


def _cache_clear() -> None:
    _cache.clear()


def _cache_size() -> int:
    return len(_cache)


def cached(ttl_seconds: int):
    """Decorator: cache successful results for ttl_seconds; LRU evict at cap.

    Exceptions are NOT cached — callers can retry transient failures.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__module__, fn.__qualname__, args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            if key in _cache:
                ts, value = _cache[key]
                if now - ts < ttl_seconds:
                    _cache.move_to_end(key)
                    return value
                del _cache[key]
            value = fn(*args, **kwargs)  # may raise — not cached
            _cache[key] = (now, value)
            _cache.move_to_end(key)
            while len(_cache) > MAX_CACHE_ENTRIES:
                _cache.popitem(last=False)
            return value
        return wrapper
    return decorator


def _base_opts(extra: dict | None = None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        opts["proxy"] = proxy
    if extra:
        opts.update(extra)
    return opts


def _extract(url_or_query: str, *, extra_opts: dict | None = None) -> dict:
    """Run yt-dlp extract_info and return the raw dict.

    Raises yt-dlp exceptions on extraction failure — callers translate
    them into the `{ok: false, error: ...}` response envelope.
    """
    opts = _base_opts(extra_opts)
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url_or_query, download=False)
