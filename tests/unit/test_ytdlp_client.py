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
