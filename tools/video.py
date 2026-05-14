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
