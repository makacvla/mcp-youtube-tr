# YouTube Transcript MCP Server

MCP server for fetching YouTube video transcripts (subtitles). Works without authentication, supports automatic and manual subtitles.

Transport: **HTTP** — recommended for remote servers.

## Running

```bash
docker compose up -d --build
```

Server will be available at `http://<host>:8000/mcp`

## Proxy Configuration

The Dockerfile includes proxy settings for network environments that require them:

```dockerfile
ENV http_proxy=http://proxy.server.com:8080
ENV https_proxy=http://proxy.server.com:8080
ENV no_proxy=localhost,127.0.0.1
```

**If you don't need a proxy:**
- Remove or comment out these lines in the `Dockerfile`

**If you need different proxy settings:**
- Update the proxy URLs in the `Dockerfile` to match your network configuration

## Connecting to VS Code

Add to `mcp.json` (VS Code global settings):

```json
{
  "servers": {
    "youtube-transcript": {
      "url": "http://<host>:8000/mcp",
      "type": "http"
    }
  }
}
```

## Tools

All tools return JSON with an `ok: bool` field. Programmatic input errors (empty video, invalid range) raise; runtime errors (video not found, network) return `{"ok": false, "error": "..."}`.

### Transcript

| Tool | Params | Notes |
|------|--------|-------|
| `get_transcript` | `video`, `languages="en,ru"`, `timestamps=true` | Full transcript with optional `[MM:SS]` |
| `list_available_transcripts` | `video` | Available languages + auto/manual flag |
| `get_transcript_chunk` | `video`, `from_sec`, `to_sec`, `languages="en,ru"`, `timestamps=true` | Time-range slice |
| `search_in_transcript` | `video`, `query`, `languages="en,ru"`, `context_chars=50` | Case-insensitive search with timestamps |

### Video metadata

| Tool | Params | Notes |
|------|--------|-------|
| `get_video_info` | `video` | Title, channel, duration, views, description, tags |
| `get_video_chapters` | `video` | Chapter titles + start/end seconds (may be empty) |
| `get_thumbnail_url` | `video`, `quality="max"` | One of `max`, `high`, `medium`, `default` |

### Discovery

| Tool | Params | Notes |
|------|--------|-------|
| `search_videos` | `query`, `max_results=10` (cap 50) | YouTube search |
| `get_channel_info` | `channel` | `@handle`, full URL, or UC… ID |
| `list_channel_videos` | `channel`, `max_results=20` (cap 100) | Recent uploads |
| `get_playlist_videos` | `playlist`, `max_results=50` (cap 200) | Playlist ID or full URL |

`video` accepts ID or any URL: `watch?v=…`, `youtu.be/…`, `shorts/…`, `embed/…`.

## Testing

```bash
pip install -r requirements-dev.txt
pytest                       # unit only (fast)
pytest --run-integration     # also hit real YouTube
```
