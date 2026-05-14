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
