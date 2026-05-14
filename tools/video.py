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


def get_video_chapters(video: str) -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")
    video_id = extract_video_id(video)
    try:
        info = _info(video_id)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "video_id": video_id})

    chapters_raw = info.get("chapters") or []
    chapters = [
        {
            "title": c.get("title", ""),
            "start_sec": int(c.get("start_time", 0)),
            "end_sec": int(c.get("end_time", 0)),
        }
        for c in chapters_raw
    ]
    return _dumps({"ok": True, "video_id": video_id, "chapters": chapters})


_QUALITY_PRIORITY = {
    "max": ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"],
    "high": ["hqdefault", "sddefault", "mqdefault", "default"],
    "medium": ["mqdefault", "default"],
    "default": ["default"],
}


def get_thumbnail_url(video: str, quality: str = "max") -> str:
    if not video or not video.strip():
        raise ValueError("video must be a non-empty string")
    if quality not in _QUALITY_PRIORITY:
        raise ValueError(f"quality must be one of {list(_QUALITY_PRIORITY)}")

    video_id = extract_video_id(video)
    try:
        info = _info(video_id)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "video_id": video_id})

    thumbs = info.get("thumbnails") or []
    by_id = {t.get("id"): t for t in thumbs}
    for tid in _QUALITY_PRIORITY[quality]:
        t = by_id.get(tid)
        if t and t.get("url"):
            return _dumps({
                "ok": True,
                "video_id": video_id,
                "url": t["url"],
                "width": t.get("width"),
                "height": t.get("height"),
                "quality": quality,
            })

    # fallback to top-level thumbnail
    fallback = info.get("thumbnail")
    if fallback:
        return _dumps({
            "ok": True,
            "video_id": video_id,
            "url": fallback,
            "width": None,
            "height": None,
            "quality": quality,
        })

    return _dumps({"ok": False, "error": "no thumbnail available", "video_id": video_id})
