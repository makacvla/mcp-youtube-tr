import json

from ytdlp_client import _extract, cached


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


SEARCH_CAP = 50


@cached(ttl_seconds=300)
def _search(query: str, n: int) -> dict:
    return _extract(f"ytsearch{n}:{query}", extra_opts={"extract_flat": True})


def search_videos(query: str, max_results: int = 10) -> str:
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    if max_results < 1 or max_results > SEARCH_CAP:
        raise ValueError(f"max_results must be between 1 and {SEARCH_CAP}")

    try:
        info = _search(query.strip().lower(), max_results)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "query": query})

    results = []
    for e in info.get("entries", []) or []:
        if not e:
            continue
        results.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "channel": e.get("channel") or e.get("uploader"),
            "duration_sec": e.get("duration"),
            "view_count": e.get("view_count"),
            "upload_date": e.get("upload_date"),
            "url": e.get("webpage_url") or e.get("url"),
        })
    return _dumps({"ok": True, "query": query, "results": results})


def _channel_url(channel: str) -> str:
    c = channel.strip()
    if c.startswith("http://") or c.startswith("https://"):
        return c
    if c.startswith("@"):
        return f"https://www.youtube.com/{c}"
    if c.startswith("UC") and len(c) > 20:
        return f"https://www.youtube.com/channel/{c}"
    return f"https://www.youtube.com/@{c.lstrip('@')}"


@cached(ttl_seconds=900)
def _channel(url: str) -> dict:
    return _extract(url, extra_opts={"extract_flat": True, "playlistend": 1})


def get_channel_info(channel: str) -> str:
    if not channel or not channel.strip():
        raise ValueError("channel must be a non-empty string")
    url = _channel_url(channel)
    try:
        info = _channel(url)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "channel": channel})

    return _dumps({
        "ok": True,
        "id": info.get("channel_id") or info.get("id"),
        "title": info.get("channel") or info.get("title"),
        "subscriber_count": info.get("channel_follower_count"),
        "video_count": info.get("playlist_count"),
        "description": info.get("description"),
        "url": info.get("webpage_url") or url,
    })


CHANNEL_VIDEOS_CAP = 100


@cached(ttl_seconds=600)
def _channel_videos(url: str, n: int) -> dict:
    return _extract(url, extra_opts={"extract_flat": True, "playlistend": n})


PLAYLIST_CAP = 200


def _playlist_url(playlist: str) -> str:
    p = playlist.strip()
    if p.startswith("http://") or p.startswith("https://"):
        return p
    return f"https://www.youtube.com/playlist?list={p}"


@cached(ttl_seconds=900)
def _playlist(url: str, n: int) -> dict:
    return _extract(url, extra_opts={"extract_flat": True, "playlistend": n})


def list_channel_videos(channel: str, max_results: int = 20) -> str:
    if not channel or not channel.strip():
        raise ValueError("channel must be a non-empty string")
    if max_results < 1 or max_results > CHANNEL_VIDEOS_CAP:
        raise ValueError(f"max_results must be between 1 and {CHANNEL_VIDEOS_CAP}")

    base = _channel_url(channel)
    url = base.rstrip("/") + "/videos"
    try:
        info = _channel_videos(url, max_results)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "channel": channel})

    videos = []
    for e in (info.get("entries") or [])[:max_results]:
        if not e:
            continue
        videos.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "duration_sec": e.get("duration"),
            "upload_date": e.get("upload_date"),
            "view_count": e.get("view_count"),
        })
    return _dumps({
        "ok": True,
        "channel_id": info.get("channel_id") or info.get("id"),
        "channel_title": info.get("channel") or info.get("title"),
        "videos": videos,
    })


def get_playlist_videos(playlist: str, max_results: int = 50) -> str:
    if not playlist or not playlist.strip():
        raise ValueError("playlist must be a non-empty string")
    if max_results < 1 or max_results > PLAYLIST_CAP:
        raise ValueError(f"max_results must be between 1 and {PLAYLIST_CAP}")

    url = _playlist_url(playlist)
    try:
        info = _playlist(url, max_results)
    except Exception as e:
        return _dumps({"ok": False, "error": str(e), "playlist": playlist})

    videos = []
    for i, e in enumerate((info.get("entries") or [])[:max_results], start=1):
        if not e:
            continue
        videos.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "duration_sec": e.get("duration"),
            "channel": e.get("channel") or e.get("uploader"),
            "position": i,
        })
    return _dumps({
        "ok": True,
        "playlist_id": info.get("id"),
        "title": info.get("title"),
        "video_count": info.get("playlist_count") or len(videos),
        "videos": videos,
    })
