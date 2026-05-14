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
