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
