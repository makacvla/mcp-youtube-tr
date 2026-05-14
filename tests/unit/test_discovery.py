import json
from unittest.mock import patch
import pytest

from tools.discovery import search_videos, get_channel_info


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
    assert "ytsearch2:" in ext.call_args[0][0]


def test_search_videos_caps_max_results():
    with pytest.raises(ValueError):
        search_videos("q", max_results=999)


def test_search_videos_raises_on_empty_query():
    with pytest.raises(ValueError):
        search_videos("", max_results=5)


def test_search_videos_raises_on_zero():
    with pytest.raises(ValueError):
        search_videos("q", max_results=0)


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
    with pytest.raises(ValueError):
        get_channel_info("")
