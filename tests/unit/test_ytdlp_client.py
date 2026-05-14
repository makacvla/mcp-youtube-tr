import pytest
import time
from unittest.mock import patch, MagicMock
from ytdlp_client import extract_video_id, cached, _cache_clear, _cache_size, MAX_CACHE_ENTRIES


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
