import json
from unittest.mock import patch, MagicMock

import pytest

from tools.transcript import get_transcript, list_available_transcripts


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
    # also fail the fallback fetch
    track.fetch.side_effect = Exception("fallback failed too")

    with patch("tools.transcript.YouTubeTranscriptApi", return_value=api):
        out = json.loads(get_transcript("dQw4w9WgXcQ", languages="ru"))

    assert out["ok"] is False
    assert "error" in out
    assert out["tried_languages"] == ["ru"]


def test_get_transcript_raises_on_empty_video():
    with pytest.raises(ValueError):
        get_transcript("", languages="en")


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
