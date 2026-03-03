from __future__ import annotations

import os
import re
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

BASE_URL = os.getenv("SECOND_BRAIN_URL", "http://localhost:8088").rstrip("/")
TIMEOUT_SECONDS = float(os.getenv("SECOND_BRAIN_TIMEOUT_SECONDS", "20"))
DEFAULT_PROJECT = os.getenv("SECOND_BRAIN_DEFAULT_PROJECT", "").strip()
API_KEY = os.getenv("SECOND_BRAIN_API_KEY", "").strip()
API_KEY_HEADER = os.getenv("SECOND_BRAIN_API_KEY_HEADER", "X-Second-Brain-Key").strip() or "X-Second-Brain-Key"
MAX_LIMIT = 200
DEFAULT_SCAN_LIMIT = 120

mcp = FastMCP("second-brain")


def _clamp_limit(value: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, MAX_LIMIT))


def _request_headers() -> dict[str, str]:
    if not API_KEY:
        return {}
    return {API_KEY_HEADER: API_KEY}


def _request(method: str, path: str, *, payload: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = requests.request(
            method=method,
            url=f"{BASE_URL}{path}",
            json=payload,
            params=params,
            timeout=TIMEOUT_SECONDS,
            headers=_request_headers(),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"gateway request failed ({method} {path}): {exc.__class__.__name__}") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"gateway returned non-JSON response ({method} {path})") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"gateway returned unexpected payload type ({method} {path})")
    return data


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", path, payload=payload)


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    return _request("GET", path, params=params)


def _normalize_project(project: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", project.strip()).strip("-").lower()
    if not value:
        raise ValueError("project must contain letters or numbers")
    return value


def _normalize_tag(tag: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._:-]+", "-", tag.strip()).strip("-").lower()


def _normalize_tags(tags: list[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in tags or []:
        if not isinstance(raw, str):
            continue
        value = _normalize_tag(raw)
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _project_tag(project: str) -> str:
    return f"project:{_normalize_project(project)}"


def _tags_with_project(tags: list[str] | None, project: str) -> list[str]:
    merged = _normalize_tags(tags)
    tag = _project_tag(project)
    if tag not in merged:
        merged.append(tag)
    return merged


def _tags_with_optional_default_project(tags: list[str] | None) -> list[str]:
    if not DEFAULT_PROJECT:
        return _normalize_tags(tags)
    return _tags_with_project(tags, DEFAULT_PROJECT)


def _sanitize_note(item: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = ("id", "content", "tags", "source", "created_at", "updated_at", "rank")
    return {key: item[key] for key in allowed_keys if key in item}


def _sanitize_note_list(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            cleaned.append(_sanitize_note(item))
    return cleaned


def _sanitize_ack(data: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = ("ok", "id", "created_at", "updated_at")
    sanitized = {key: data[key] for key in allowed_keys if key in data}
    if "ok" not in sanitized:
        sanitized["ok"] = True
    return sanitized


def _filter_results_by_project(items: list[dict[str, Any]], project: str) -> list[dict[str, Any]]:
    tag = _project_tag(project)
    return [item for item in items if tag in (item.get("tags") or [])]


def _filter_project_from_recent_fallback(project: str, limit: int, scan_limit: int) -> dict[str, Any]:
    wanted = _clamp_limit(limit, 20)
    scanned = max(wanted, _clamp_limit(scan_limit, DEFAULT_SCAN_LIMIT))
    data = _get("/api/recent", {"limit": scanned})
    results = _filter_results_by_project(_sanitize_note_list(data.get("results", [])), project)[:wanted]
    return {
        "ok": data.get("ok", True),
        "project": _normalize_project(project),
        "results": results,
        "scanned": scanned,
    }


@mcp.tool()
def remember(content: str, tags: list[str] | None = None, force: bool = False) -> dict[str, Any]:
    """Store a note in second brain memory."""
    data = _post("/api/remember", {"content": content, "tags": _tags_with_optional_default_project(tags), "force": bool(force)})
    return _sanitize_ack(data)


@mcp.tool()
def recall(query: str, limit: int = 10) -> dict[str, Any]:
    """Recall notes from second brain memory."""
    wanted = _clamp_limit(limit, 10)
    data = _post("/api/recall", {"query": query, "limit": wanted})
    return {"ok": data.get("ok", True), "results": _sanitize_note_list(data.get("results", []))}


@mcp.tool()
def recent(limit: int = 20) -> dict[str, Any]:
    """Get recent notes from second brain memory."""
    wanted = _clamp_limit(limit, 20)
    data = _get("/api/recent", {"limit": wanted})
    return {"ok": data.get("ok", True), "results": _sanitize_note_list(data.get("results", []))}


@mcp.tool()
def forget(id: str) -> dict[str, Any]:
    """Soft-delete a note by id."""
    data = _post("/api/forget", {"id": id})
    return _sanitize_ack(data)


@mcp.tool()
def remember_for_project(project: str, content: str, tags: list[str] | None = None, force: bool = False) -> dict[str, Any]:
    """Store a note with project namespace tag (project:<name>)."""
    data = _post("/api/remember", {"content": content, "tags": _tags_with_project(tags, project), "force": bool(force)})
    return _sanitize_ack(data)


@mcp.tool()
def recall_for_project(project: str, query: str, limit: int = 10, scan_limit: int = 60) -> dict[str, Any]:
    """
    Recall notes for one project.

    Strategy:
    1) Prefer gateway-side project filtering.
    2) Fallback to client-side filtering for older gateways.
    """
    wanted = _clamp_limit(limit, 10)
    normalized_project = _normalize_project(project)
    try:
        data = _post("/api/recall", {"query": query, "limit": wanted, "project": normalized_project})
        return {
            "ok": data.get("ok", True),
            "project": normalized_project,
            "results": _sanitize_note_list(data.get("results", [])),
            "strategy": "server-filter",
            "scanned": wanted,
        }
    except RuntimeError:
        scanned = max(wanted, _clamp_limit(scan_limit, DEFAULT_SCAN_LIMIT))
        semantic = _post("/api/recall", {"query": query, "limit": scanned})
        filtered = _filter_results_by_project(_sanitize_note_list(semantic.get("results", [])), normalized_project)[:wanted]
        if filtered:
            return {
                "ok": semantic.get("ok", True),
                "project": normalized_project,
                "results": filtered,
                "strategy": "fallback-semantic+client-filter",
                "scanned": scanned,
            }
        fallback = _filter_project_from_recent_fallback(normalized_project, wanted, scanned)
        fallback["strategy"] = "fallback-recent+client-filter"
        return fallback


@mcp.tool()
def recent_for_project(project: str, limit: int = 20, scan_limit: int = 120) -> dict[str, Any]:
    """
    Get recent notes for one project.

    Strategy:
    1) Prefer gateway-side project filtering.
    2) Fallback to client-side filtering for older gateways.
    """
    wanted = _clamp_limit(limit, 20)
    normalized_project = _normalize_project(project)
    try:
        data = _get("/api/recent", {"limit": wanted, "project": normalized_project})
        return {
            "ok": data.get("ok", True),
            "project": normalized_project,
            "results": _sanitize_note_list(data.get("results", [])),
            "strategy": "server-filter",
            "scanned": wanted,
        }
    except RuntimeError:
        fallback = _filter_project_from_recent_fallback(normalized_project, wanted, scan_limit)
        fallback["strategy"] = "fallback-recent+client-filter"
        return fallback


@mcp.tool()
def list_projects(scan_limit: int = 300) -> dict[str, Any]:
    """
    List project namespaces.

    Strategy:
    1) Prefer dedicated gateway endpoint `/api/projects`.
    2) Fallback to scanning recent notes for older gateways.
    """
    scanned = _clamp_limit(scan_limit, DEFAULT_SCAN_LIMIT)
    try:
        data = _get("/api/projects", {"limit": scanned})
        projects: list[dict[str, Any]] = []
        for row in data.get("projects", []) if isinstance(data.get("projects", []), list) else []:
            if not isinstance(row, dict):
                continue
            project = str(row.get("project", "")).strip().lower()
            if not project:
                continue
            projects.append({"project": project, "count": int(row.get("count", 0))})
        return {"ok": data.get("ok", True), "projects": projects, "scanned": scanned, "strategy": "server-projects-endpoint"}
    except RuntimeError:
        data = _get("/api/recent", {"limit": scanned})
        counts: dict[str, int] = {}
        for item in _sanitize_note_list(data.get("results", [])):
            for tag in item.get("tags") or []:
                if not isinstance(tag, str) or not tag.startswith("project:"):
                    continue
                project = tag.split(":", 1)[1].strip().lower()
                if not project:
                    continue
                counts[project] = counts.get(project, 0) + 1
        projects = [{"project": name, "count": counts[name]} for name in sorted(counts)]
        return {"ok": data.get("ok", True), "projects": projects, "scanned": scanned, "strategy": "fallback-recent-scan"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
