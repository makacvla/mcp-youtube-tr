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
    lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]
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


def list_available_transcripts(video: str) -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")
    video_id = extract_video_id(video)
    try:
        transcripts = _list_tracks(video_id)
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
