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

## Tool: `get_transcript`

| Parameter    | Type   | Default     | Description                                   |
|-------------|--------|-------------|-----------------------------------------------|
| `video`     | string | —           | Video ID or full URL                           |
| `languages` | string | `"en,ru"`   | Language priority, comma-separated             |
| `timestamps`| bool   | `true`      | Include timestamps                             |

### Usage Examples

```
Get transcript for video https://youtube.com/shorts/6MIdV-qFjIc

Show subtitles for dQw4w9WgXcQ in Russian
```

## Testing

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"capabilities":{},"protocolVersion":"0.1.0","clientInfo":{"name":"test","version":"1.0"}}}'
```
