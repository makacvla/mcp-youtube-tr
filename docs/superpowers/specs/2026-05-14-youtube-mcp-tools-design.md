# YouTube MCP — Expansion to A/B/C Tool Bundles

**Status:** APPROVED — all sections (1–6) confirmed by user. Ready for implementation planning.

## Context

Existing server (`server.py`, FastMCP v2 HTTP, port 8000) exposes one tool: `get_transcript`. Goal: add 10 new anonymous tools across three bundles.

**Locked decisions:**
- Library for metadata/discovery: **yt-dlp** (chosen over pytubefix and InnerTube)
- Existing `get_transcript` keeps the same signature and behavior; response gains an additive `"ok": true/false` field (see Section 3)
- Anonymous only — no API key, no auth
- Out of scope: bundle D (comments)

## Section 1 — Code structure (APPROVED)

```
mcp-youtube-tr/
├── server.py          # FastMCP setup + @mcp.tool() registrations only
├── tools/
│   ├── __init__.py
│   ├── transcript.py  # bundle C
│   ├── video.py       # bundle A
│   └── discovery.py   # bundle B
├── ytdlp_client.py    # thin wrapper: yt-dlp options, proxy from env, timeouts
└── ...
```

`server.py` becomes thin: each `@mcp.tool()` delegates to a function in `tools/*`. `ytdlp_client.py` centralizes `quiet=True`, `extract_flat`, `skip_download=True`, proxy resolution.

## Section 2 — Tool signatures (APPROVED)

All tools return `str` (JSON, `ensure_ascii=False, indent=2`) — matches existing `get_transcript` pattern. All accept video/channel/playlist as URL or ID.

### Bundle A — `tools/video.py`

| Tool | Params | Returns |
|------|--------|---------|
| `get_video_info` | `video: str` | `{id, title, channel, channel_id, duration_sec, upload_date, view_count, like_count, description, tags, thumbnail_url}` |
| `get_video_chapters` | `video: str` | `{video_id, chapters: [{title, start_sec, end_sec}]}` |
| `get_thumbnail_url` | `video: str`, `quality: str = "max"` (one of: `max`, `high`, `medium`, `default`) | `{video_id, url, width, height, quality}` |

### Bundle B — `tools/discovery.py`

| Tool | Params | Returns |
|------|--------|---------|
| `search_videos` | `query: str`, `max_results: int = 10` (cap 50) | `{query, results: [{id, title, channel, duration_sec, view_count, upload_date, url}]}` |
| `get_channel_info` | `channel: str` (URL/`@handle`/ID) | `{id, title, subscriber_count, video_count, description, url}` |
| `list_channel_videos` | `channel: str`, `max_results: int = 20` (cap 100) | `{channel_id, channel_title, videos: [{id, title, duration_sec, upload_date, view_count}]}` |
| `get_playlist_videos` | `playlist: str`, `max_results: int = 50` (cap 200) | `{playlist_id, title, video_count, videos: [{id, title, duration_sec, channel, position}]}` |

### Bundle C — `tools/transcript.py`

| Tool | Params | Returns |
|------|--------|---------|
| `get_transcript` | (unchanged) | (unchanged) |
| `list_available_transcripts` | `video: str` | `{video_id, transcripts: [{language, language_code, is_generated}]}` |
| `search_in_transcript` | `video: str`, `query: str`, `languages: str = "en,ru"`, `context_chars: int = 50` | `{video_id, query, language, matches: [{timestamp_sec, formatted_timestamp: "MM:SS", text, context}]}` |
| `get_transcript_chunk` | `video: str`, `from_sec: int`, `to_sec: int`, `languages: str = "en,ru"`, `timestamps: bool = true` | `{video_id, language, from_sec, to_sec, transcript}` |

## Section 3 — Error model (APPROVED — hybrid)

**Rule:** raise exceptions for programmatic errors only; return JSON with `error` field for everything else. Every response includes an explicit `ok: bool` flag.

### Raise (programmatic errors only)

`raise ValueError(...)` when input is malformed — empty `video`, negative `max_results`, `to_sec < from_sec`, unknown `quality`. These are caller bugs, not business outcomes. FastMCP converts the exception into an MCP protocol-level error.

### Return JSON with `error` field (business / runtime errors)

Everything else returns a JSON object with `ok: false` and rich context:
- Video not found / unavailable / age-gated / private
- Network or yt-dlp extraction failure
- No transcript in requested languages
- Channel or playlist not found

Context fields included where useful (e.g., `available_transcripts`, `tried_languages`, `video_id`). Keeps the LLM able to recover (try a different language, suggest alternatives).

### Response shape — all tools

```jsonc
// Success
{ "ok": true, "video_id": "...", "title": "...", /* ...tool-specific data */ }

// Soft fail
{ "ok": false,
  "error": "No transcript in requested languages",
  "video_id": "...",
  "tried_languages": ["ru"],
  "available_transcripts": [/* ... */] }
```

### Migration of existing `get_transcript`

Add `"ok": true` on the success path and `"ok": false` alongside the existing `"error"` field on failure paths (server.py:76, 99, 121). No field removal — purely additive. Existing clients keep working; new clients can branch on `ok`.

## Section 4 — Caching (APPROVED — in-memory TTL)

In-memory TTL cache in `ytdlp_client.py`. Lives for the process; lost on container restart (acceptable).

### Per-tool TTLs

| Tool | TTL | Rationale |
|------|-----|-----------|
| `get_video_info`, `get_video_chapters`, `get_thumbnail_url` | 1 h | metadata rarely changes |
| `list_available_transcripts`, `get_transcript`, `get_transcript_chunk`, `search_in_transcript` | 6 h | transcripts effectively static |
| `get_channel_info`, `get_playlist_videos` | 15 min | changes occasionally |
| `list_channel_videos` | 10 min | new uploads appear |
| `search_videos` | 5 min | query results are time-sensitive |

### Implementation

- Plain `dict` keyed by `(tool_name, normalized_args_tuple)` → `(timestamp, payload)`
- Decorator `@cached(ttl_seconds)` applied to internal yt-dlp helpers (not to `@mcp.tool()` directly — keeps caching transparent to the tool layer)
- LRU eviction at **500 entries** (cap memory; effectively unlimited for normal use)
- Cache only stores **successful** results — failures (`ok: false`) are not cached, so retries can succeed
- Normalization: lowercase query strings, resolve URLs to canonical IDs before keying

### What is NOT cached

- Failed lookups (would block legitimate retries after transient errors)
- Tool calls returning programmatic errors (those raise — never reach cache)

## Section 5 — Testing (APPROVED — hybrid)

Tool: `pytest`. Test directory: `tests/`.

### Unit tests (always run)

`tests/unit/` — patched `yt_dlp.YoutubeDL.extract_info` returns fixture dicts. Coverage targets:
- `extract_video_id` — every URL format + plain ID
- Channel/playlist URL normalization
- Cache: hit, miss, expiry, LRU eviction, failures not cached
- Error model: which inputs raise vs return `ok: false`
- Response shape: `ok` present everywhere; success/failure invariants

Fast (seconds), deterministic, no network. Run by default with `pytest`.

### Integration smoke test (opt-in)

`tests/integration/test_smoke.py` — marked `@pytest.mark.integration`, **skipped by default**. Run via `pytest --run-integration` before deploy.

Calls real yt-dlp + youtube-transcript-api against known-stable inputs:
- Video: `dQw4w9WgXcQ` (Rick Astley — extremely unlikely to disappear)
- Channel: `@YouTube` (official channel)
- Search: `"never gonna give you up"`

Verifies: each new tool returns `ok: true` and expected top-level fields. Does NOT assert on volatile fields (view counts, etc.) — just shape.

### Out of scope

- `pytest-benchmark` performance tests
- End-to-end MCP-over-HTTP tests (Dockerfile `HEALTHCHECK` already smoke-tests the JSON-RPC layer in production)
- Mutation testing

### CI

No CI is configured today. If added later, run unit tests on every PR; integration manually before deploy.

## Section 6 — Deployment & rollout (APPROVED)

Server lives on `10.57.202.171` at `/build/MCP/mcp-youtube-tr/mcp-youtube-tr/` (see memory `reference-deployment`). Single-container Docker Compose. Proxy `cache.konts.lv:8080`.

### Rollout steps

1. Implement + unit-test locally
2. Bump `requirements.txt`: add `yt-dlp` pinned to the latest stable release at implementation time (verify on PyPI; pin major version, e.g. `yt-dlp>=2026.X.0,<2027.0.0`)
3. Run `pytest --run-integration` locally to confirm smoke against real YouTube
4. Commit + push to repo
5. On `10.57.202.171`:
   ```
   cd /build/MCP/mcp-youtube-tr/mcp-youtube-tr/
   git pull
   docker compose up -d --build
   docker logs -f youtube-mcp-server  # watch startup
   ```
6. Verify healthcheck passes (`docker inspect youtube-mcp-server --format '{{.State.Health.Status}}'` → `healthy`)
7. Test from connected client (VS Code / Claude) — call one tool from each bundle

### Backward compatibility

- `get_transcript` remains: response gains `"ok": true/false`; no field removed; default args unchanged
- New tools are additive — clients that don't know them keep working

### Risk and rollback

- If yt-dlp install bloats image significantly, evaluate slim variant or pin to specific version
- Rollback: `git revert` + rebuild. Old container has no state to preserve.
- yt-dlp can break on YouTube updates — pinning major version + monthly review recommended after initial deploy

### Out of scope for this change

- Multi-instance / scaling
- Persistent cache (Redis)
- Authentication / rate-limiting (server is on internal network)

## Next step

Hand off to `writing-plans` skill to produce a sequenced implementation plan (file-by-file, test-driven where applicable).
