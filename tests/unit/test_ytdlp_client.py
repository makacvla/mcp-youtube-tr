import pytest
import time
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
