import json
from unittest.mock import patch
import pytest

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
    with pytest.raises(ValueError):
        get_video_info("")
