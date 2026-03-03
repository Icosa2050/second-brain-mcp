# second-brain-mcp

Standalone MCP server that bridges Codex (or any MCP client) to a second-brain HTTP gateway.

## Tools
- `remember(content, tags=[], force=false)`
- `recall(query, limit=10)`
- `recent(limit=20)`
- `forget(id)`
- `remember_for_project(project, content, tags=[], force=false)`
- `recall_for_project(project, query, limit=10, scan_limit=60)`
- `recent_for_project(project, limit=20, scan_limit=120)`
- `list_projects(scan_limit=300)`

Project notes use tag namespace `project:<name>` (for example `project:kostula`).

## Environment
- `SECOND_BRAIN_URL` (default: `http://localhost:8088`)
- `SECOND_BRAIN_TIMEOUT_SECONDS` (default: `20`)
- `SECOND_BRAIN_DEFAULT_PROJECT` (optional; auto-adds `project:<name>` tag in `remember`)
- `SECOND_BRAIN_API_KEY` (optional; sent as header for gateway auth)
- `SECOND_BRAIN_API_KEY_HEADER` (default: `X-Second-Brain-Key`)

## Local run
```bash
python -m venv .venv
.venv/bin/pip install -e .
SECOND_BRAIN_URL=http://localhost:8088 .venv/bin/second-brain-mcp
```

The process uses stdio transport (for MCP clients).

## Gateway API contract
Expected endpoints:
- `POST /api/remember` with `{"content": "...", "tags": ["..."], "force": false}`
- `POST /api/recall` with `{"query": "...", "limit": 10, "project": "optional", "tags": ["optional"]}`
- `GET /api/recent?limit=20&project=optional&tags=comma,separated`
- `GET /api/projects?limit=200`
- `POST /api/forget` with `{"id": "..."}`

Expected response shape:
- Ack responses: `{"ok": true, "id": "...", "created_at": "...", "updated_at": "..."}`
- List responses: `{"ok": true, "results": [ ...notes ]}`

Note shape consumed by MCP:
- `id`, `content`, `tags`, `source`, `created_at`, `updated_at`, optional `rank`

## Project namespacing
Project tools namespace memories with tag `project:<name>`.

Current behavior:
- `recall_for_project` requests gateway-side filtering via `project`.
- `recent_for_project` requests gateway-side filtering via `project`.
- `list_projects` uses gateway endpoint `/api/projects`.

Backward compatibility:
- If the gateway does not support these filters/endpoints yet, MCP falls back to client-side filtering of recent/recall results.

## Security notes
- Do not expose your gateway on the public internet without auth.
- Prefer API-key auth (`SECOND_BRAIN_API_KEY`) and TLS at your reverse proxy.
- This MCP bridge intentionally avoids storing DB credentials; it only calls your gateway.
- If gateway secret-guard blocks a note, you can intentionally override with `force=true` in `remember`/`remember_for_project`.
