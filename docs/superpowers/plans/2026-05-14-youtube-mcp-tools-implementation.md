# YouTube MCP A/B/C Tools — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand YouTube MCP server from 1 tool to 11 tools across video-metadata, discovery, and transcript bundles — anonymous (no API key) via yt-dlp + youtube-transcript-api, with hybrid error model, in-memory TTL cache, and additive backward-compatible migration of existing `get_transcript`.

**Architecture:** Refactor existing `server.py` into a thin FastMCP registration layer that delegates to focused modules in `tools/` (`transcript.py`, `video.py`, `discovery.py`). A shared `ytdlp_client.py` wraps yt-dlp setup (proxy, timeouts) and provides the `@cached(ttl)` decorator with LRU eviction. Tests split into fast `tests/unit/` (mocked yt-dlp) and opt-in `tests/integration/` (real network).

**Tech Stack:** Python 3.12, FastMCP v2 (HTTP transport), youtube-transcript-api ≥ 1.2, yt-dlp (pinned major), pytest, Docker.

**Spec:** `docs/superpowers/specs/2026-05-14-youtube-mcp-tools-design.md`

---

## File Layout

**Create:**
- `ytdlp_client.py` — yt-dlp wrapper, proxy, `extract_video_id`, `@cached` decorator
- `tools/__init__.py` — empty package marker
- `tools/transcript.py` — `get_transcript`, `list_available_transcripts`, `search_in_transcript`, `get_transcript_chunk`
- `tools/video.py` — `get_video_info`, `get_video_chapters`, `get_thumbnail_url`
- `tools/discovery.py` — `search_videos`, `get_channel_info`, `list_channel_videos`, `get_playlist_videos`
- `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`
- `tests/conftest.py` — shared fixtures
- `tests/unit/test_ytdlp_client.py`
- `tests/unit/test_transcript.py`
- `tests/unit/test_video.py`
- `tests/unit/test_discovery.py`
- `tests/integration/test_smoke.py`
- `pytest.ini` — registers `integration` marker + `--run-integration` option
- `requirements-dev.txt` — pytest

**Modify:**
- `server.py` — strip business logic; keep FastMCP setup + `@mcp.tool()` delegations
- `requirements.txt` — add `yt-dlp`
- `README.md` — document new tools

---

## Task 1: Test infrastructure

**Files:**
- Create: `pytest.ini`
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
markers =
    integration: hits real YouTube; skipped unless --run-integration is given
addopts = -ra --strict-markers
```

- [ ] **Step 2: Create `requirements-dev.txt`**

```
pytest>=8.0,<9.0
```

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that hit real YouTube",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(reason="need --run-integration to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def _isolate_cache():
    """Clear the global ytdlp_client cache between tests so mocks don't leak."""
    try:
        from ytdlp_client import _cache_clear
    except ImportError:
        yield
        return
    _cache_clear()
    yield
    _cache_clear()
```

- [ ] **Step 4: Create empty `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`**

Each file is empty (zero bytes).

- [ ] **Step 5: Verify pytest discovers nothing yet but runs cleanly**

Run: `pip install -r requirements-dev.txt && pytest -v`
Expected: `no tests ran` exit code 5 OR `0 passed` exit code 0; no errors.

- [ ] **Step 6: Commit**

```bash
git add pytest.ini requirements-dev.txt tests/
git commit -m "#noissue add pytest infrastructure with integration opt-in"
```

---

## Task 2: `extract_video_id` moved to `ytdlp_client.py` (with tests)

**Files:**
- Create: `ytdlp_client.py`
- Create: `tests/unit/test_ytdlp_client.py`

- [ ] **Step 1: Write failing test for `extract_video_id`**

Create `tests/unit/test_ytdlp_client.py`:

```python
import pytest
from ytdlp_client import extract_video_id


@pytest.mark.parametrize("inp,expected", [
    ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("  dQw4w9WgXcQ  ", "dQw4w9WgXcQ"),
])
def test_extract_video_id_valid(inp, expected):
    assert extract_video_id(inp) == expected


def test_extract_video_id_passthrough_unknown():
    # not a recognized pattern — pass through as-is
    assert extract_video_id("some-random-string") == "some-random-string"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_ytdlp_client.py -v`
Expected: `ModuleNotFoundError: No module named 'ytdlp_client'`

- [ ] **Step 3: Create minimal `ytdlp_client.py` with `extract_video_id`**

```python
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
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/unit/test_ytdlp_client.py -v`
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add ytdlp_client.py tests/unit/test_ytdlp_client.py
git commit -m "#noissue extract video_id helper into ytdlp_client module"
```

---

## Task 3: `@cached(ttl)` decorator with LRU eviction

**Files:**
- Modify: `ytdlp_client.py`
- Modify: `tests/unit/test_ytdlp_client.py`

- [ ] **Step 1: Write failing tests for cache**

Append to `tests/unit/test_ytdlp_client.py`:

```python
import time
from ytdlp_client import cached, _cache_clear, _cache_size, MAX_CACHE_ENTRIES


def setup_function():
    _cache_clear()


def test_cache_hit_returns_cached_value():
    calls = []

    @cached(ttl_seconds=60)
    def f(x):
        calls.append(x)
        return x * 2

    assert f(3) == 6
    assert f(3) == 6
    assert calls == [3]  # called once


def test_cache_miss_on_different_args():
    @cached(ttl_seconds=60)
    def f(x):
        return x * 2

    assert f(1) == 2
    assert f(2) == 4
    assert _cache_size() == 2


def test_cache_expires_after_ttl(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr("ytdlp_client.time.monotonic", lambda: fake_now[0])

    calls = []

    @cached(ttl_seconds=10)
    def f(x):
        calls.append(x)
        return x

    f(7)
    fake_now[0] = 1011.0  # past TTL
    f(7)
    assert calls == [7, 7]


def test_cache_does_not_store_exceptions():
    calls = []

    @cached(ttl_seconds=60)
    def f():
        calls.append(1)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        f()
    with pytest.raises(RuntimeError):
        f()
    assert len(calls) == 2  # called twice, not cached


def test_cache_lru_eviction():
    @cached(ttl_seconds=60)
    def f(x):
        return x

    for i in range(MAX_CACHE_ENTRIES + 10):
        f(i)
    assert _cache_size() == MAX_CACHE_ENTRIES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_ytdlp_client.py -v`
Expected: `ImportError` for `cached`, `_cache_clear`, `_cache_size`, `MAX_CACHE_ENTRIES`.

- [ ] **Step 3: Implement cache in `ytdlp_client.py`**

Append to `ytdlp_client.py`:

```python
import time
from collections import OrderedDict
from functools import wraps

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
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/test_ytdlp_client.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add ytdlp_client.py tests/unit/test_ytdlp_client.py
git commit -m "#noissue add TTL+LRU cache decorator"
```

---

## Task 4: yt-dlp wrapper `_extract` with proxy + base options

**Files:**
- Modify: `ytdlp_client.py`
- Modify: `requirements.txt`
- Modify: `tests/unit/test_ytdlp_client.py`

- [ ] **Step 1: Add `yt-dlp` to `requirements.txt`**

Append to `requirements.txt`:

```
yt-dlp>=2026.4.0,<2027.0.0
```

(yt-dlp uses CalVer `YYYY.MM.DD`. Pin floor to a recent release as of implementation; cap to next year. If `pip install` fails to resolve, run `pip index versions yt-dlp | head -3` and bump the floor.)

- [ ] **Step 2: Write failing test for `_extract`**

Append to `tests/unit/test_ytdlp_client.py`:

```python
from unittest.mock import patch, MagicMock


def test_extract_calls_ytdl_with_base_opts():
    fake_info = {"id": "abc", "title": "T"}
    with patch("ytdlp_client.YoutubeDL") as YDL:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        instance.extract_info.return_value = fake_info
        YDL.return_value = instance

        from ytdlp_client import _extract
        result = _extract("https://youtu.be/abc")

    assert result == fake_info
    opts = YDL.call_args[0][0]
    assert opts["quiet"] is True
    assert opts["skip_download"] is True
    assert opts["no_warnings"] is True
    instance.extract_info.assert_called_once_with(
        "https://youtu.be/abc", download=False
    )


def test_extract_passes_proxy_from_env(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://corp.proxy:8080")
    with patch("ytdlp_client.YoutubeDL") as YDL:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        instance.extract_info.return_value = {}
        YDL.return_value = instance

        from ytdlp_client import _extract
        _extract("https://youtu.be/abc")

    assert YDL.call_args[0][0]["proxy"] == "http://corp.proxy:8080"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_ytdlp_client.py::test_extract_calls_ytdl_with_base_opts -v`
Expected: `ImportError: cannot import name '_extract'`.

- [ ] **Step 4: Implement `_extract`**

Append to `ytdlp_client.py`:

```python
import os
from yt_dlp import YoutubeDL


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
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/test_ytdlp_client.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add ytdlp_client.py requirements.txt tests/unit/test_ytdlp_client.py
git commit -m "#noissue add yt-dlp wrapper with proxy + base opts"
```

---

## Task 5: Migrate `get_transcript` into `tools/transcript.py` with `ok` field

Goal: move existing logic out of `server.py` into `tools/transcript.py`, add `"ok": true/false` field on all return paths, no other behavior change.

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/transcript.py`
- Create: `tests/unit/test_transcript.py`
- Modify: `server.py`

- [ ] **Step 1: Create empty `tools/__init__.py`**

Zero bytes.

- [ ] **Step 2: Write failing test for `get_transcript` shape**

Create `tests/unit/test_transcript.py`:

```python
import json
from unittest.mock import patch, MagicMock

import pytest

from tools.transcript import get_transcript


class _Entry:
    def __init__(self, text, start):
        self.text = text
        self.start = start


def _mock_api(transcripts_list, fetch_map):
    api = MagicMock()
    api.list.return_value = transcripts_list
    api.fetch.side_effect = lambda vid, languages: fetch_map[languages[0]]
    return api


def test_get_transcript_success_includes_ok_true():
    track = MagicMock(language="English", language_code="en", is_generated=False)
    api = _mock_api([track], {"en": [_Entry("hello", 0.0), _Entry("world", 1.5)]})

    with patch("tools.transcript.YouTubeTranscriptApi", return_value=api):
        out = json.loads(get_transcript("dQw4w9WgXcQ", languages="en"))

    assert out["ok"] is True
    assert out["language"] == "en"
    assert "[00:00] hello" in out["transcript"]
    assert "[00:01] world" in out["transcript"]


def test_get_transcript_no_languages_returns_ok_false():
    track = MagicMock(language="English", language_code="en", is_generated=False)
    api = MagicMock()
    api.list.return_value = [track]
    api.fetch.side_effect = Exception("no transcript")

    with patch("tools.transcript.YouTubeTranscriptApi", return_value=api):
        # also fail the fallback fetch
        track.fetch.side_effect = Exception("fallback failed too")
        out = json.loads(get_transcript("dQw4w9WgXcQ", languages="ru"))

    assert out["ok"] is False
    assert "error" in out
    assert out["tried_languages"] == ["ru"]


def test_get_transcript_raises_on_empty_video():
    import pytest
    with pytest.raises(ValueError):
        get_transcript("", languages="en")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_transcript.py -v`
Expected: `ModuleNotFoundError: No module named 'tools.transcript'`.

- [ ] **Step 4: Implement `tools/transcript.py` (migrated from `server.py`, with cached helpers)**

Create `tools/transcript.py`:

```python
import json

from youtube_transcript_api import YouTubeTranscriptApi

from ytdlp_client import extract_video_id, cached

_TRANSCRIPT_TTL = 6 * 3600  # spec: 6h


def _get_entry_field(entry, field: str):
    """Compatibility helper for dict-style (< 0.6) and object-style (>= 0.6) entries."""
    if isinstance(entry, dict):
        return entry[field]
    return getattr(entry, field)


def _format_entries(entries, with_timestamps: bool) -> str:
    lines = []
    for entry in entries:
        text = _get_entry_field(entry, "text")
        if with_timestamps:
            start = _get_entry_field(entry, "start")
            minutes = int(start // 60)
            seconds = int(start % 60)
            lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


@cached(ttl_seconds=_TRANSCRIPT_TTL)
def _list_tracks(video_id: str):
    """Return list of available transcript track objects. Raises on failure."""
    return list(YouTubeTranscriptApi().list(video_id))


@cached(ttl_seconds=_TRANSCRIPT_TTL)
def _fetch_lang(video_id: str, lang: str):
    """Fetch transcript entries for a specific language. Raises on failure."""
    return YouTubeTranscriptApi().fetch(video_id, languages=[lang])


def get_transcript(video: str, languages: str = "en,ru", timestamps: bool = True) -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")

    video_id = extract_video_id(video)
    lang_list = [l.strip() for l in languages.split(",") if l.strip()]
    if not lang_list:
        raise ValueError("languages must contain at least one code")

    try:
        transcript_list = _list_tracks(video_id)
        available_info = [
            {"language": t.language, "language_code": t.language_code, "is_generated": t.is_generated}
            for t in transcript_list
        ]
    except Exception as e:
        return _dumps({"ok": False, "error": f"Could not list transcripts: {e}", "video_id": video_id})

    transcript = None
    used_lang = None
    errors = []
    for lang in lang_list:
        try:
            transcript = _fetch_lang(video_id, lang)
            used_lang = lang
            break
        except Exception as e:
            errors.append(f"{lang}: {e}")

    if transcript is None:
        try:
            first = transcript_list[0]
            transcript = first.fetch()
            used_lang = first.language_code
        except Exception as e:
            return _dumps({
                "ok": False,
                "error": f"Could not fetch any transcript: {e}",
                "tried_languages": lang_list,
                "errors": errors,
                "available_transcripts": available_info,
                "video_id": video_id,
            })

    return _dumps({
        "ok": True,
        "video_id": video_id,
        "language": used_lang,
        "available_transcripts": available_info,
        "transcript": _format_entries(transcript, timestamps),
    })
```

Note: the unit test mocks `YouTubeTranscriptApi` at the module level, which patches the class used inside both cached helpers. Cache state is module-global — tests reset it via `_cache_clear()` (re-export it from `ytdlp_client` in the test setup if needed).

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/test_transcript.py -v`
Expected: all 3 tests pass.

- [ ] **Step 6: Rewrite `server.py` to delegate**

Replace `server.py` with:

```python
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


def _signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, shutting down gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    logger.info("Starting YouTube Transcript MCP Server...")
    mcp.run(transport="http", host="0.0.0.0", port=8000, json_response=True)
```

- [ ] **Step 7: Smoke-check server still imports**

Run: `python -c "import server; print(server.mcp)"`
Expected: prints the FastMCP instance, no error.

- [ ] **Step 8: Commit**

```bash
git add tools/ server.py tests/unit/test_transcript.py
git commit -m "#noissue refactor get_transcript into tools/ + add ok field"
```

---

## Task 6: `list_available_transcripts`

**Files:**
- Modify: `tools/transcript.py`
- Modify: `tests/unit/test_transcript.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_transcript.py`:

```python
from tools.transcript import list_available_transcripts


def test_list_available_transcripts_success():
    t1 = MagicMock(language="English", language_code="en", is_generated=False)
    t2 = MagicMock(language="Russian (auto)", language_code="ru", is_generated=True)
    api = MagicMock()
    api.list.return_value = [t1, t2]

    with patch("tools.transcript.YouTubeTranscriptApi", return_value=api):
        out = json.loads(list_available_transcripts("dQw4w9WgXcQ"))

    assert out["ok"] is True
    assert out["video_id"] == "dQw4w9WgXcQ"
    assert len(out["transcripts"]) == 2
    assert out["transcripts"][0]["language_code"] == "en"
    assert out["transcripts"][1]["is_generated"] is True


def test_list_available_transcripts_error_returns_ok_false():
    api = MagicMock()
    api.list.side_effect = Exception("not found")

    with patch("tools.transcript.YouTubeTranscriptApi", return_value=api):
        out = json.loads(list_available_transcripts("dQw4w9WgXcQ"))

    assert out["ok"] is False
    assert "error" in out
    assert out["video_id"] == "dQw4w9WgXcQ"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_transcript.py::test_list_available_transcripts_success -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement in `tools/transcript.py`**

Append:

```python
def list_available_transcripts(video: str) -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")
    video_id = extract_video_id(video)
    api = YouTubeTranscriptApi()
    try:
        transcripts = list(api.list(video_id))
    except Exception as e:
        return _dumps({"ok": False, "error": f"Could not list transcripts: {e}", "video_id": video_id})

    return _dumps({
        "ok": True,
        "video_id": video_id,
        "transcripts": [
            {"language": t.language, "language_code": t.language_code, "is_generated": t.is_generated}
            for t in transcripts
        ],
    })
```

- [ ] **Step 4: Register in `server.py`**

Append to `server.py` (before `_signal_handler`):

```python
@mcp.tool()
def list_available_transcripts(video: str) -> str:
    """List all available transcript tracks for a YouTube video without fetching content.

    Args:
        video: YouTube video ID or full URL
    """
    return t_transcript.list_available_transcripts(video)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_transcript.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/transcript.py server.py tests/unit/test_transcript.py
git commit -m "#noissue add list_available_transcripts tool"
```

---

## Task 7: `get_transcript_chunk`

**Files:**
- Modify: `tools/transcript.py`
- Modify: `tests/unit/test_transcript.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_transcript.py`:

```python
from tools.transcript import get_transcript_chunk


def test_get_transcript_chunk_filters_by_time():
    track = MagicMock(language="English", language_code="en", is_generated=False)
    entries = [
        _Entry("before", 5.0),
        _Entry("inside-a", 15.0),
        _Entry("inside-b", 25.0),
        _Entry("after", 50.0),
    ]
    api = _mock_api([track], {"en": entries})

    with patch("tools.transcript.YouTubeTranscriptApi", return_value=api):
        out = json.loads(get_transcript_chunk("dQw4w9WgXcQ", 10, 30, languages="en"))

    assert out["ok"] is True
    assert out["from_sec"] == 10
    assert out["to_sec"] == 30
    assert "inside-a" in out["transcript"]
    assert "inside-b" in out["transcript"]
    assert "before" not in out["transcript"]
    assert "after" not in out["transcript"]


def test_get_transcript_chunk_raises_on_invalid_range():
    import pytest
    with pytest.raises(ValueError):
        get_transcript_chunk("dQw4w9WgXcQ", 50, 10)


def test_get_transcript_chunk_raises_on_negative():
    import pytest
    with pytest.raises(ValueError):
        get_transcript_chunk("dQw4w9WgXcQ", -1, 10)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_transcript.py -v`
Expected: ImportError on `get_transcript_chunk`.

- [ ] **Step 3: Implement**

Append to `tools/transcript.py`:

```python
def _fetch_first_available(api, video_id, lang_list):
    """Return (entries, used_lang_code) or (None, errors_list)."""
    errors = []
    for lang in lang_list:
        try:
            return api.fetch(video_id, languages=[lang]), lang, None
        except Exception as e:
            errors.append(f"{lang}: {e}")
    return None, None, errors


def get_transcript_chunk(
    video: str,
    from_sec: int,
    to_sec: int,
    languages: str = "en,ru",
    timestamps: bool = True,
) -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")
    if from_sec < 0:
        raise ValueError("from_sec must be >= 0")
    if to_sec <= from_sec:
        raise ValueError("to_sec must be greater than from_sec")

    video_id = extract_video_id(video)
    lang_list = [l.strip() for l in languages.split(",") if l.strip()]
    if not lang_list:
        raise ValueError("languages must contain at least one code")

    api = YouTubeTranscriptApi()
    entries, used_lang, errors = _fetch_first_available(api, video_id, lang_list)
    if entries is None:
        return _dumps({
            "ok": False,
            "error": "Could not fetch transcript in any requested language",
            "video_id": video_id,
            "tried_languages": lang_list,
            "errors": errors,
        })

    in_range = [
        e for e in entries
        if from_sec <= _get_entry_field(e, "start") < to_sec
    ]
    return _dumps({
        "ok": True,
        "video_id": video_id,
        "language": used_lang,
        "from_sec": from_sec,
        "to_sec": to_sec,
        "transcript": _format_entries(in_range, timestamps),
    })
```

- [ ] **Step 4: Register in `server.py`**

Append to `server.py`:

```python
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
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_transcript.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/transcript.py server.py tests/unit/test_transcript.py
git commit -m "#noissue add get_transcript_chunk tool"
```

---

## Task 8: `search_in_transcript`

**Files:**
- Modify: `tools/transcript.py`
- Modify: `tests/unit/test_transcript.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_transcript.py`:

```python
from tools.transcript import search_in_transcript


def test_search_in_transcript_finds_matches_case_insensitive():
    track = MagicMock(language="English", language_code="en", is_generated=False)
    entries = [
        _Entry("Hello world", 5.0),
        _Entry("nothing here", 10.0),
        _Entry("say hello again", 15.0),
    ]
    api = _mock_api([track], {"en": entries})

    with patch("tools.transcript.YouTubeTranscriptApi", return_value=api):
        out = json.loads(search_in_transcript("dQw4w9WgXcQ", "hello", languages="en"))

    assert out["ok"] is True
    assert out["query"] == "hello"
    assert len(out["matches"]) == 2
    assert out["matches"][0]["formatted_timestamp"] == "00:05"
    assert out["matches"][1]["formatted_timestamp"] == "00:15"
    assert "Hello world" in out["matches"][0]["text"]


def test_search_in_transcript_no_matches_returns_empty_list():
    track = MagicMock(language="English", language_code="en", is_generated=False)
    api = _mock_api([track], {"en": [_Entry("nothing", 0.0)]})

    with patch("tools.transcript.YouTubeTranscriptApi", return_value=api):
        out = json.loads(search_in_transcript("dQw4w9WgXcQ", "missing", languages="en"))

    assert out["ok"] is True
    assert out["matches"] == []


def test_search_in_transcript_raises_on_empty_query():
    import pytest
    with pytest.raises(ValueError):
        search_in_transcript("dQw4w9WgXcQ", "")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_transcript.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Append to `tools/transcript.py`:

```python
def search_in_transcript(
    video: str,
    query: str,
    languages: str = "en,ru",
    context_chars: int = 50,
) -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    if context_chars < 0:
        raise ValueError("context_chars must be >= 0")

    video_id = extract_video_id(video)
    lang_list = [l.strip() for l in languages.split(",") if l.strip()]
    if not lang_list:
        raise ValueError("languages must contain at least one code")

    api = YouTubeTranscriptApi()
    entries, used_lang, errors = _fetch_first_available(api, video_id, lang_list)
    if entries is None:
        return _dumps({
            "ok": False,
            "error": "Could not fetch transcript in any requested language",
            "video_id": video_id,
            "tried_languages": lang_list,
            "errors": errors,
        })

    q_lower = query.lower()
    matches = []
    for entry in entries:
        text = _get_entry_field(entry, "text")
        idx = text.lower().find(q_lower)
        if idx == -1:
            continue
        start = _get_entry_field(entry, "start")
        ctx_start = max(0, idx - context_chars)
        ctx_end = min(len(text), idx + len(query) + context_chars)
        matches.append({
            "timestamp_sec": start,
            "formatted_timestamp": f"{int(start // 60):02d}:{int(start % 60):02d}",
            "text": text,
            "context": text[ctx_start:ctx_end],
        })

    return _dumps({
        "ok": True,
        "video_id": video_id,
        "query": query,
        "language": used_lang,
        "matches": matches,
    })
```

- [ ] **Step 4: Register in `server.py`**

Append:

```python
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
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_transcript.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/transcript.py server.py tests/unit/test_transcript.py
git commit -m "#noissue add search_in_transcript tool"
```

---

## Task 9: `get_video_info`

**Files:**
- Create: `tools/video.py`
- Create: `tests/unit/test_video.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_video.py`:

```python
import json
from unittest.mock import patch
from tools.video import get_video_info


FAKE_INFO = {
    "id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "uploader": "Rick Astley",
    "channel": "Rick Astley",
    "channel_id": "UC...",
    "duration": 213,
    "upload_date": "20091025",
    "view_count": 1_500_000_000,
    "like_count": 10_000_000,
    "description": "The official video...",
    "tags": ["music", "80s"],
    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
}


def test_get_video_info_success():
    with patch("tools.video._extract", return_value=FAKE_INFO):
        out = json.loads(get_video_info("dQw4w9WgXcQ"))

    assert out["ok"] is True
    assert out["id"] == "dQw4w9WgXcQ"
    assert out["title"].startswith("Rick Astley")
    assert out["duration_sec"] == 213
    assert out["channel"] == "Rick Astley"
    assert out["thumbnail_url"].endswith(".jpg")


def test_get_video_info_extraction_failure_returns_ok_false():
    with patch("tools.video._extract", side_effect=Exception("video unavailable")):
        out = json.loads(get_video_info("dQw4w9WgXcQ"))

    assert out["ok"] is False
    assert "video unavailable" in out["error"]
    assert out["video_id"] == "dQw4w9WgXcQ"


def test_get_video_info_raises_on_empty():
    import pytest
    with pytest.raises(ValueError):
        get_video_info("")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_video.py -v`
Expected: `ModuleNotFoundError: tools.video`.

- [ ] **Step 3: Implement `tools/video.py`**

```python
import json

from ytdlp_client import extract_video_id, _extract, cached


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


@cached(ttl_seconds=3600)
def _info(video_id: str) -> dict:
    return _extract(f"https://www.youtube.com/watch?v={video_id}")


def get_video_info(video: str) -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")
    video_id = extract_video_id(video)
    try:
        info = _info(video_id)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "video_id": video_id})

    return _dumps({
        "ok": True,
        "id": info.get("id"),
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "channel_id": info.get("channel_id"),
        "duration_sec": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "description": info.get("description"),
        "tags": info.get("tags", []),
        "thumbnail_url": info.get("thumbnail"),
    })
```

- [ ] **Step 4: Register in `server.py`**

Add import at top:

```python
from tools import video as t_video
```

Add tool:

```python
@mcp.tool()
def get_video_info(video: str) -> str:
    """Fetch metadata about a YouTube video without watching it.

    Args:
        video: YouTube video ID or full URL
    """
    return t_video.get_video_info(video)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_video.py -v && pytest tests/unit/test_ytdlp_client.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/video.py tests/unit/test_video.py server.py
git commit -m "#noissue add get_video_info tool"
```

---

## Task 10: `get_video_chapters`

**Files:**
- Modify: `tools/video.py`
- Modify: `tests/unit/test_video.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_video.py`:

```python
from tools.video import get_video_chapters


def test_get_video_chapters_returns_chapters():
    info = {
        "id": "abc",
        "chapters": [
            {"title": "Intro", "start_time": 0.0, "end_time": 30.0},
            {"title": "Main", "start_time": 30.0, "end_time": 180.0},
        ],
    }
    with patch("tools.video._extract", return_value=info):
        out = json.loads(get_video_chapters("abc"))

    assert out["ok"] is True
    assert len(out["chapters"]) == 2
    assert out["chapters"][0]["title"] == "Intro"
    assert out["chapters"][0]["start_sec"] == 0
    assert out["chapters"][1]["end_sec"] == 180


def test_get_video_chapters_empty_when_no_chapters():
    info = {"id": "abc", "chapters": None}
    with patch("tools.video._extract", return_value=info):
        out = json.loads(get_video_chapters("abc"))

    assert out["ok"] is True
    assert out["chapters"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_video.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Append to `tools/video.py`:

```python
def get_video_chapters(video: str) -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")
    video_id = extract_video_id(video)
    try:
        info = _info(video_id)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "video_id": video_id})

    chapters_raw = info.get("chapters") or []
    chapters = [
        {
            "title": c.get("title", ""),
            "start_sec": int(c.get("start_time", 0)),
            "end_sec": int(c.get("end_time", 0)),
        }
        for c in chapters_raw
    ]
    return _dumps({"ok": True, "video_id": video_id, "chapters": chapters})
```

- [ ] **Step 4: Register in `server.py`**

```python
@mcp.tool()
def get_video_chapters(video: str) -> str:
    """Fetch chapter markers (title + start/end seconds) for a YouTube video.

    Args:
        video: YouTube video ID or full URL
    """
    return t_video.get_video_chapters(video)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_video.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/video.py server.py tests/unit/test_video.py
git commit -m "#noissue add get_video_chapters tool"
```

---

## Task 11: `get_thumbnail_url`

**Files:**
- Modify: `tools/video.py`
- Modify: `tests/unit/test_video.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_video.py`:

```python
from tools.video import get_thumbnail_url


def test_get_thumbnail_url_max_quality():
    info = {
        "id": "abc",
        "thumbnails": [
            {"id": "default", "url": "https://i.ytimg.com/vi/abc/default.jpg", "width": 120, "height": 90},
            {"id": "mqdefault", "url": "https://i.ytimg.com/vi/abc/mqdefault.jpg", "width": 320, "height": 180},
            {"id": "hqdefault", "url": "https://i.ytimg.com/vi/abc/hqdefault.jpg", "width": 480, "height": 360},
            {"id": "maxresdefault", "url": "https://i.ytimg.com/vi/abc/maxresdefault.jpg", "width": 1280, "height": 720},
        ],
        "thumbnail": "https://i.ytimg.com/vi/abc/maxresdefault.jpg",
    }
    with patch("tools.video._extract", return_value=info):
        out = json.loads(get_thumbnail_url("abc", quality="max"))

    assert out["ok"] is True
    assert "maxresdefault" in out["url"]
    assert out["width"] == 1280
    assert out["quality"] == "max"


def test_get_thumbnail_url_default_quality():
    info = {
        "id": "abc",
        "thumbnails": [
            {"id": "default", "url": "https://i.ytimg.com/vi/abc/default.jpg", "width": 120, "height": 90},
            {"id": "maxresdefault", "url": "https://i.ytimg.com/vi/abc/maxresdefault.jpg", "width": 1280, "height": 720},
        ],
    }
    with patch("tools.video._extract", return_value=info):
        out = json.loads(get_thumbnail_url("abc", quality="default"))

    assert out["width"] == 120


def test_get_thumbnail_url_raises_on_unknown_quality():
    import pytest
    with pytest.raises(ValueError):
        get_thumbnail_url("abc", quality="ultra")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_video.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Append to `tools/video.py`:

```python
_QUALITY_PRIORITY = {
    "max": ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"],
    "high": ["hqdefault", "sddefault", "mqdefault", "default"],
    "medium": ["mqdefault", "default"],
    "default": ["default"],
}


def get_thumbnail_url(video: str, quality: str = "max") -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")
    if quality not in _QUALITY_PRIORITY:
        raise ValueError(f"quality must be one of {list(_QUALITY_PRIORITY)}")

    video_id = extract_video_id(video)
    try:
        info = _info(video_id)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "video_id": video_id})

    thumbs = info.get("thumbnails") or []
    by_id = {t.get("id"): t for t in thumbs}
    for tid in _QUALITY_PRIORITY[quality]:
        t = by_id.get(tid)
        if t and t.get("url"):
            return _dumps({
                "ok": True,
                "video_id": video_id,
                "url": t["url"],
                "width": t.get("width"),
                "height": t.get("height"),
                "quality": quality,
            })

    # fallback to top-level thumbnail
    fallback = info.get("thumbnail")
    if fallback:
        return _dumps({
            "ok": True,
            "video_id": video_id,
            "url": fallback,
            "width": None,
            "height": None,
            "quality": quality,
        })

    return _dumps({"ok": False, "error": "no thumbnail available", "video_id": video_id})
```

- [ ] **Step 4: Register in `server.py`**

```python
@mcp.tool()
def get_thumbnail_url(video: str, quality: str = "max") -> str:
    """Get a thumbnail URL for a YouTube video at the requested quality.

    Args:
        video: YouTube video ID or full URL
        quality: One of "max", "high", "medium", "default" (default: "max")
    """
    return t_video.get_thumbnail_url(video, quality)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_video.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/video.py server.py tests/unit/test_video.py
git commit -m "#noissue add get_thumbnail_url tool"
```

---

## Task 12: `search_videos`

**Files:**
- Create: `tools/discovery.py`
- Create: `tests/unit/test_discovery.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_discovery.py`:

```python
import json
from unittest.mock import patch
from tools.discovery import search_videos


SEARCH_RESULT = {
    "entries": [
        {
            "id": "abc",
            "title": "First match",
            "channel": "Channel A",
            "duration": 120,
            "view_count": 1000,
            "upload_date": "20240101",
            "webpage_url": "https://www.youtube.com/watch?v=abc",
        },
        {
            "id": "def",
            "title": "Second match",
            "channel": "Channel B",
            "duration": 240,
            "view_count": 2000,
            "upload_date": "20240102",
            "webpage_url": "https://www.youtube.com/watch?v=def",
        },
    ]
}


def test_search_videos_success():
    with patch("tools.discovery._extract", return_value=SEARCH_RESULT) as ext:
        out = json.loads(search_videos("test query", max_results=2))

    assert out["ok"] is True
    assert out["query"] == "test query"
    assert len(out["results"]) == 2
    assert out["results"][0]["id"] == "abc"
    assert out["results"][0]["duration_sec"] == 120
    # called with ytsearch2:
    assert "ytsearch2:" in ext.call_args[0][0]


def test_search_videos_caps_max_results():
    import pytest
    with pytest.raises(ValueError):
        search_videos("q", max_results=999)


def test_search_videos_raises_on_empty_query():
    import pytest
    with pytest.raises(ValueError):
        search_videos("", max_results=5)


def test_search_videos_raises_on_zero():
    import pytest
    with pytest.raises(ValueError):
        search_videos("q", max_results=0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_discovery.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `tools/discovery.py`**

```python
import json

from ytdlp_client import _extract, cached


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


SEARCH_CAP = 50


@cached(ttl_seconds=300)
def _search(query: str, n: int) -> dict:
    return _extract(f"ytsearch{n}:{query}", extra_opts={"extract_flat": True})


def search_videos(query: str, max_results: int = 10) -> str:
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    if max_results < 1 or max_results > SEARCH_CAP:
        raise ValueError(f"max_results must be between 1 and {SEARCH_CAP}")

    try:
        info = _search(query.strip().lower(), max_results)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "query": query})

    results = []
    for e in info.get("entries", []) or []:
        if not e:
            continue
        results.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "channel": e.get("channel") or e.get("uploader"),
            "duration_sec": e.get("duration"),
            "view_count": e.get("view_count"),
            "upload_date": e.get("upload_date"),
            "url": e.get("webpage_url") or e.get("url"),
        })
    return _dumps({"ok": True, "query": query, "results": results})
```

- [ ] **Step 4: Register in `server.py`**

```python
from tools import discovery as t_discovery


@mcp.tool()
def search_videos(query: str, max_results: int = 10) -> str:
    """Search YouTube and return the top N videos with metadata.

    Args:
        query: Search query string
        max_results: Number of results, 1 to 50 (default: 10)
    """
    return t_discovery.search_videos(query, max_results)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_discovery.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/discovery.py tests/unit/test_discovery.py server.py
git commit -m "#noissue add search_videos tool"
```

---

## Task 13: `get_channel_info`

**Files:**
- Modify: `tools/discovery.py`
- Modify: `tests/unit/test_discovery.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_discovery.py`:

```python
from tools.discovery import get_channel_info


CHANNEL_INFO = {
    "id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
    "channel": "Google Developers",
    "title": "Google Developers",
    "channel_follower_count": 2_500_000,
    "playlist_count": 50,
    "description": "Channel for devs",
    "webpage_url": "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw",
}


def test_get_channel_info_from_handle():
    with patch("tools.discovery._extract", return_value=CHANNEL_INFO):
        out = json.loads(get_channel_info("@GoogleDevelopers"))

    assert out["ok"] is True
    assert out["id"].startswith("UC")
    assert out["title"] == "Google Developers"
    assert out["subscriber_count"] == 2_500_000


def test_get_channel_info_raises_on_empty():
    import pytest
    with pytest.raises(ValueError):
        get_channel_info("")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_discovery.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Append to `tools/discovery.py`:

```python
def _channel_url(channel: str) -> str:
    c = channel.strip()
    if c.startswith("http://") or c.startswith("https://"):
        return c
    if c.startswith("@"):
        return f"https://www.youtube.com/{c}"
    if c.startswith("UC") and len(c) > 20:
        return f"https://www.youtube.com/channel/{c}"
    return f"https://www.youtube.com/@{c.lstrip('@')}"


@cached(ttl_seconds=900)
def _channel(url: str) -> dict:
    return _extract(url, extra_opts={"extract_flat": True, "playlistend": 1})


def get_channel_info(channel: str) -> str:
    if not channel or not channel.strip():
        raise ValueError("channel must be a non-empty string")
    url = _channel_url(channel)
    try:
        info = _channel(url)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "channel": channel})

    return _dumps({
        "ok": True,
        "id": info.get("channel_id") or info.get("id"),
        "title": info.get("channel") or info.get("title"),
        "subscriber_count": info.get("channel_follower_count"),
        "video_count": info.get("playlist_count"),
        "description": info.get("description"),
        "url": info.get("webpage_url") or url,
    })
```

- [ ] **Step 4: Register in `server.py`**

```python
@mcp.tool()
def get_channel_info(channel: str) -> str:
    """Fetch metadata for a YouTube channel (handle, URL, or UC… ID).

    Args:
        channel: @handle, full channel URL, or UC… channel ID
    """
    return t_discovery.get_channel_info(channel)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_discovery.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/discovery.py server.py tests/unit/test_discovery.py
git commit -m "#noissue add get_channel_info tool"
```

---

## Task 14: `list_channel_videos`

**Files:**
- Modify: `tools/discovery.py`
- Modify: `tests/unit/test_discovery.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_discovery.py`:

```python
from tools.discovery import list_channel_videos


CHANNEL_VIDEOS = {
    "id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
    "channel": "Google Developers",
    "entries": [
        {"id": "v1", "title": "Video 1", "duration": 600, "view_count": 1000, "upload_date": "20240101"},
        {"id": "v2", "title": "Video 2", "duration": 300, "view_count": 500, "upload_date": "20240102"},
    ],
}


def test_list_channel_videos_success():
    with patch("tools.discovery._extract", return_value=CHANNEL_VIDEOS):
        out = json.loads(list_channel_videos("@GoogleDevelopers", max_results=2))

    assert out["ok"] is True
    assert out["channel_title"] == "Google Developers"
    assert len(out["videos"]) == 2
    assert out["videos"][0]["id"] == "v1"


def test_list_channel_videos_cap():
    import pytest
    with pytest.raises(ValueError):
        list_channel_videos("@x", max_results=999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_discovery.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Append to `tools/discovery.py`:

```python
CHANNEL_VIDEOS_CAP = 100


@cached(ttl_seconds=600)
def _channel_videos(url: str, n: int) -> dict:
    return _extract(url, extra_opts={"extract_flat": True, "playlistend": n})


def list_channel_videos(channel: str, max_results: int = 20) -> str:
    if not channel or not channel.strip():
        raise ValueError("channel must be a non-empty string")
    if max_results < 1 or max_results > CHANNEL_VIDEOS_CAP:
        raise ValueError(f"max_results must be between 1 and {CHANNEL_VIDEOS_CAP}")

    # use /videos path so yt-dlp returns the uploads playlist, not the channel home
    base = _channel_url(channel)
    url = base.rstrip("/") + "/videos"
    try:
        info = _channel_videos(url, max_results)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "channel": channel})

    videos = []
    for e in (info.get("entries") or [])[:max_results]:
        if not e:
            continue
        videos.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "duration_sec": e.get("duration"),
            "upload_date": e.get("upload_date"),
            "view_count": e.get("view_count"),
        })
    return _dumps({
        "ok": True,
        "channel_id": info.get("channel_id") or info.get("id"),
        "channel_title": info.get("channel") or info.get("title"),
        "videos": videos,
    })
```

- [ ] **Step 4: Register in `server.py`**

```python
@mcp.tool()
def list_channel_videos(channel: str, max_results: int = 20) -> str:
    """List recent videos from a YouTube channel.

    Args:
        channel: @handle, full channel URL, or UC… channel ID
        max_results: Number of videos to return, 1 to 100 (default: 20)
    """
    return t_discovery.list_channel_videos(channel, max_results)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_discovery.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/discovery.py server.py tests/unit/test_discovery.py
git commit -m "#noissue add list_channel_videos tool"
```

---

## Task 15: `get_playlist_videos`

**Files:**
- Modify: `tools/discovery.py`
- Modify: `tests/unit/test_discovery.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_discovery.py`:

```python
from tools.discovery import get_playlist_videos


PLAYLIST_INFO = {
    "id": "PLxxx",
    "title": "My playlist",
    "playlist_count": 3,
    "entries": [
        {"id": "v1", "title": "V1", "duration": 100, "channel": "Ch1"},
        {"id": "v2", "title": "V2", "duration": 200, "channel": "Ch2"},
        {"id": "v3", "title": "V3", "duration": 300, "channel": "Ch3"},
    ],
}


def test_get_playlist_videos_success():
    with patch("tools.discovery._extract", return_value=PLAYLIST_INFO):
        out = json.loads(get_playlist_videos("PLxxx", max_results=3))

    assert out["ok"] is True
    assert out["playlist_id"] == "PLxxx"
    assert out["video_count"] == 3
    assert len(out["videos"]) == 3
    assert out["videos"][0]["position"] == 1
    assert out["videos"][2]["position"] == 3


def test_get_playlist_videos_url_passthrough():
    with patch("tools.discovery._extract", return_value=PLAYLIST_INFO) as ext:
        get_playlist_videos("https://www.youtube.com/playlist?list=PLxxx", max_results=3)
    assert "list=PLxxx" in ext.call_args[0][0]


def test_get_playlist_videos_cap():
    import pytest
    with pytest.raises(ValueError):
        get_playlist_videos("PLxxx", max_results=99999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_discovery.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Append to `tools/discovery.py`:

```python
PLAYLIST_CAP = 200


def _playlist_url(playlist: str) -> str:
    p = playlist.strip()
    if p.startswith("http://") or p.startswith("https://"):
        return p
    return f"https://www.youtube.com/playlist?list={p}"


@cached(ttl_seconds=900)
def _playlist(url: str, n: int) -> dict:
    return _extract(url, extra_opts={"extract_flat": True, "playlistend": n})


def get_playlist_videos(playlist: str, max_results: int = 50) -> str:
    if not playlist or not playlist.strip():
        raise ValueError("playlist must be a non-empty string")
    if max_results < 1 or max_results > PLAYLIST_CAP:
        raise ValueError(f"max_results must be between 1 and {PLAYLIST_CAP}")

    url = _playlist_url(playlist)
    try:
        info = _playlist(url, max_results)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "playlist": playlist})

    videos = []
    for i, e in enumerate((info.get("entries") or [])[:max_results], start=1):
        if not e:
            continue
        videos.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "duration_sec": e.get("duration"),
            "channel": e.get("channel") or e.get("uploader"),
            "position": i,
        })
    return _dumps({
        "ok": True,
        "playlist_id": info.get("id"),
        "title": info.get("title"),
        "video_count": info.get("playlist_count") or len(videos),
        "videos": videos,
    })
```

- [ ] **Step 4: Register in `server.py`**

```python
@mcp.tool()
def get_playlist_videos(playlist: str, max_results: int = 50) -> str:
    """List videos in a YouTube playlist.

    Args:
        playlist: Playlist ID (PL…) or full playlist URL
        max_results: Number of videos to return, 1 to 200 (default: 50)
    """
    return t_discovery.get_playlist_videos(playlist, max_results)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_discovery.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/discovery.py server.py tests/unit/test_discovery.py
git commit -m "#noissue add get_playlist_videos tool"
```

---

## Task 16: Integration smoke tests

**Files:**
- Create: `tests/integration/test_smoke.py`

- [ ] **Step 1: Create `tests/integration/test_smoke.py`**

```python
"""Smoke tests against real YouTube. Run with `pytest --run-integration`."""

import json

import pytest

pytestmark = pytest.mark.integration

RICK_VIDEO = "dQw4w9WgXcQ"


def _assert_ok(payload):
    out = json.loads(payload)
    assert out["ok"] is True, f"expected ok=true, got: {out}"
    return out


def test_get_transcript_real():
    from tools.transcript import get_transcript
    out = _assert_ok(get_transcript(RICK_VIDEO, languages="en"))
    assert "transcript" in out and out["transcript"]


def test_list_available_transcripts_real():
    from tools.transcript import list_available_transcripts
    out = _assert_ok(list_available_transcripts(RICK_VIDEO))
    assert len(out["transcripts"]) >= 1


def test_get_video_info_real():
    from tools.video import get_video_info
    out = _assert_ok(get_video_info(RICK_VIDEO))
    assert out["id"] == RICK_VIDEO
    assert out["duration_sec"] is not None
    assert "Rick" in out["title"] or "rick" in out["title"].lower()


def test_get_video_chapters_real():
    from tools.video import get_video_chapters
    out = _assert_ok(get_video_chapters(RICK_VIDEO))
    assert "chapters" in out  # may be empty for this video; shape only


def test_get_thumbnail_url_real():
    from tools.video import get_thumbnail_url
    out = _assert_ok(get_thumbnail_url(RICK_VIDEO))
    assert out["url"].startswith("https://")


def test_search_videos_real():
    from tools.discovery import search_videos
    out = _assert_ok(search_videos("never gonna give you up", max_results=3))
    assert len(out["results"]) >= 1


def test_get_channel_info_real():
    from tools.discovery import get_channel_info
    out = _assert_ok(get_channel_info("@YouTube"))
    assert out["id"]


def test_list_channel_videos_real():
    from tools.discovery import list_channel_videos
    out = _assert_ok(list_channel_videos("@YouTube", max_results=3))
    assert len(out["videos"]) >= 1


def test_get_playlist_videos_real():
    """YouTube Spotlight uses a well-known stable playlist for tests."""
    from tools.discovery import get_playlist_videos
    # using one of YouTube's own historically-stable playlists
    out = _assert_ok(get_playlist_videos("PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-", max_results=3))
    assert len(out["videos"]) >= 1


def test_search_in_transcript_real():
    from tools.transcript import search_in_transcript
    out = _assert_ok(search_in_transcript(RICK_VIDEO, "never", languages="en"))
    assert len(out["matches"]) >= 1


def test_get_transcript_chunk_real():
    from tools.transcript import get_transcript_chunk
    out = _assert_ok(get_transcript_chunk(RICK_VIDEO, 0, 30, languages="en"))
    assert out["from_sec"] == 0
    assert out["to_sec"] == 30
```

- [ ] **Step 2: Verify smoke tests are skipped by default**

Run: `pytest tests/integration/ -v`
Expected: 11 tests skipped with reason "need --run-integration to run".

- [ ] **Step 3: Verify smoke tests pass with flag (network required)**

Run: `pytest tests/integration/ -v --run-integration`
Expected: all 11 pass. If any fail due to YouTube changes, investigate per-tool — do NOT mark as expected-fail.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_smoke.py
git commit -m "#noissue add integration smoke tests for all new tools"
```

---

## Task 17: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the "Tool" section with a multi-tool table**

In `README.md`, replace the existing "## Tool: `get_transcript`" section with:

```markdown
## Tools

All tools return JSON with an `ok: bool` field. Programmatic input errors (empty video, invalid range) raise; runtime errors (video not found, network) return `{"ok": false, "error": "..."}`.

### Transcript

| Tool | Params | Notes |
|------|--------|-------|
| `get_transcript` | `video`, `languages="en,ru"`, `timestamps=true` | Full transcript with optional `[MM:SS]` |
| `list_available_transcripts` | `video` | Available languages + auto/manual flag |
| `get_transcript_chunk` | `video`, `from_sec`, `to_sec`, `languages="en,ru"`, `timestamps=true` | Time-range slice |
| `search_in_transcript` | `video`, `query`, `languages="en,ru"`, `context_chars=50` | Case-insensitive search with timestamps |

### Video metadata

| Tool | Params | Notes |
|------|--------|-------|
| `get_video_info` | `video` | Title, channel, duration, views, description, tags |
| `get_video_chapters` | `video` | Chapter titles + start/end seconds (may be empty) |
| `get_thumbnail_url` | `video`, `quality="max"` | One of `max`, `high`, `medium`, `default` |

### Discovery

| Tool | Params | Notes |
|------|--------|-------|
| `search_videos` | `query`, `max_results=10` (cap 50) | YouTube search |
| `get_channel_info` | `channel` | `@handle`, full URL, or UC… ID |
| `list_channel_videos` | `channel`, `max_results=20` (cap 100) | Recent uploads |
| `get_playlist_videos` | `playlist`, `max_results=50` (cap 200) | Playlist ID or full URL |

`video` accepts ID or any URL: `watch?v=…`, `youtu.be/…`, `shorts/…`, `embed/…`.

## Testing

```bash
pip install -r requirements-dev.txt
pytest                       # unit only (fast)
pytest --run-integration     # also hit real YouTube
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "#noissue document new tools in README"
```

---

## Task 18: Deploy

**Files:** (none changed; deployment-only task)

- [ ] **Step 1: Verify full test suite passes locally**

Run: `pytest -v`
Expected: all unit tests pass; integration tests skipped.

Optional: `pytest --run-integration -v` if network available.

- [ ] **Step 2: Push to remote**

```bash
git push origin main
```

- [ ] **Step 3: Deploy on `10.57.202.171`**

```bash
ssh root@10.57.202.171 'cd /build/MCP/mcp-youtube-tr/mcp-youtube-tr/ && git pull && docker compose up -d --build'
```

- [ ] **Step 4: Wait for healthcheck to report healthy**

```bash
ssh root@10.57.202.171 'docker inspect youtube-mcp-server --format "{{.State.Health.Status}}"'
```

Expected: `healthy` (may take ~30s after startup).

- [ ] **Step 5: Tail logs briefly to confirm no errors**

```bash
ssh root@10.57.202.171 'docker logs --tail 50 youtube-mcp-server'
```

Expected: `Starting YouTube Transcript MCP Server...` then quiet healthcheck POSTs returning `200 OK`.

- [ ] **Step 6: Call one tool from each bundle via connected MCP client**

From VS Code or Claude:
- `get_transcript(video="dQw4w9WgXcQ", languages="en")` → ok=true
- `get_video_info(video="dQw4w9WgXcQ")` → ok=true, title contains "Rick"
- `search_videos(query="claude code", max_results=3)` → ok=true, ≥1 result

If any fail, roll back: `git revert HEAD && docker compose up -d --build` on the host.
