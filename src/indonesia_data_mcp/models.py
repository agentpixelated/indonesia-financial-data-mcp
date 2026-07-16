"""Shared response and provenance models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SECRET_QUERY_KEYS = {"key", "api_key", "apikey", "token", "access_token"}


def redact_url(url: str) -> str:
    """Remove credential-bearing query values before a URL leaves the server."""
    parts = urlsplit(url)
    query = [
        (key, "[REDACTED]" if key.lower() in _SECRET_QUERY_KEYS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@dataclass(frozen=True)
class Provenance:
    provider: str
    source_url: str
    retrieved_at: str
    official: bool
    source_format: str = "json"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["source_url"] = redact_url(self.source_url)
        return {key: value for key, value in result.items() if value is not None}


def envelope(
    data: Any,
    *sources: Provenance,
    warnings: list[str] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the stable, citation-first MCP response shape."""
    result: dict[str, Any] = {
        "data": data,
        "provenance": [source.to_dict() for source in sources],
    }
    if warnings:
        result["warnings"] = warnings
    if meta:
        result["meta"] = meta
    return result
