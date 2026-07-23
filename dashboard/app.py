"""Starlette dashboard app for the IDX Research Desk.

Serves a lightweight JSON API + static frontend.
Connects to the existing IDXClient for live official data.
Demo/workflow state is clearly flagged.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from indonesia_data_mcp.idx import IDXClient

STATIC_DIR = Path(__file__).parent / "static"
_TICKER_RE = re.compile(r"^[A-Z0-9]{4,8}$")


def _validate_ticker(raw: str) -> str:
    t = raw.strip().upper()
    if not _TICKER_RE.fullmatch(t):
        raise ValueError("ticker must be a 4-8 character IDX code")
    return t


VALID_STATES = {"ACTIVE", "PENDING", "COMPLETED", "FAILED"}

_SEED_MISSIONS: list[dict[str, Any]] = [
    {"id": "m-001", "title": "Deep-dive BBCA Q3 filings", "ticker": "BBCA", "state": "ACTIVE", "created_at": "2026-07-22T15:00:00Z", "demo": True},
    {"id": "m-002", "title": "Monitor BBRI announcement cycle", "ticker": "BBRI", "state": "PENDING", "created_at": "2026-07-22T14:30:00Z", "demo": True},
    {"id": "m-003", "title": "TLKM annual report extraction", "ticker": "TLKM", "state": "COMPLETED", "created_at": "2026-07-21T08:15:00Z", "demo": True},
    {"id": "m-004", "title": "ASII sector comparison", "ticker": "ASII", "state": "FAILED", "created_at": "2026-07-20T14:45:00Z", "demo": True},
]

_SEED_WATCHLIST: list[dict[str, Any]] = [
    {"ticker": "BBCA", "name": "Bank Central Asia Tbk", "sector": "Financials", "source": "local_preset", "official": False},
    {"ticker": "BBRI", "name": "Bank Rakyat Indonesia Tbk", "sector": "Financials", "source": "local_preset", "official": False},
    {"ticker": "TLKM", "name": "Telkom Indonesia Tbk", "sector": "Telecommunications", "source": "local_preset", "official": False},
    {"ticker": "ASII", "name": "Astra International Tbk", "sector": "Industrials", "source": "local_preset", "official": False},
    {"ticker": "BMRI", "name": "Bank Mandiri Tbk", "sector": "Financials", "source": "local_preset", "official": False},
]

_SEED_OPERATIONS: list[dict[str, Any]] = [
    {"id": "op-001", "type": "filing_extraction", "description": "Extract BBCA 2025 audit XBRL facts", "status": "running", "progress": 0.65, "started_at": "2026-07-22T16:00:00Z", "demo": True},
    {"id": "op-002", "type": "announcement_scan", "description": "Scan BBRI announcements for material events", "status": "queued", "progress": 0.0, "started_at": "2026-07-22T16:05:00Z", "demo": True},
    {"id": "op-003", "type": "profile_refresh", "description": "Refresh TLKM company profile and shareholders", "status": "completed", "progress": 1.0, "started_at": "2026-07-22T14:30:00Z", "demo": True},
]

_SEED_LOG: list[dict[str, Any]] = [
    {"ts": "2026-07-22T16:05:12Z", "level": "INFO", "msg": "Research Desk interface ready"},
    {"ts": "2026-07-22T16:06:00Z", "level": "INFO", "msg": "DEMO: Seeded 4 missions, 3 workflow signals"},
]


def _make_stores() -> dict[str, Any]:
    return {"missions": [dict(m) for m in _SEED_MISSIONS], "watchlist": [dict(w) for w in _SEED_WATCHLIST], "operations": [dict(o) for o in _SEED_OPERATIONS], "log": [dict(e) for e in _SEED_LOG]}


def _has_official_idx_provenance(result: dict[str, Any]) -> bool:
    provenance = result.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        return False
    for source in provenance:
        if not isinstance(source, dict):
            return False
        source_url = source.get("source_url")
        if not isinstance(source_url, str):
            return False
        parts = urlsplit(source_url)
        if (source.get("provider") != "IDX" or source.get("official") is not True or parts.scheme != "https" or (parts.hostname or "").lower() != "www.idx.co.id" or parts.username is not None or parts.password is not None or parts.port not in (None, 443)):
            return False
    return True


async def _fetch_company(idx: IDXClient, ticker: str) -> dict[str, Any]:
    try:
        result = await idx.company_profile(ticker)
        official = _has_official_idx_provenance(result)
        return {"data": result.get("data", {}), "provenance": result.get("provenance", []), "source": "official" if official else "unverified", "official": official}
    except Exception as exc:
        return {"data": {"ticker": ticker, "error": str(exc)}, "provenance": [], "source": "fallback", "official": False, "error": str(exc)}


async def _fetch_announcements(idx: IDXClient, ticker: str) -> dict[str, Any]:
    try:
        result = await idx.announcements(ticker, limit=20)
        official = _has_official_idx_provenance(result)
        return {"data": result.get("data", []), "provenance": result.get("provenance", []), "source": "official" if official else "unverified", "official": official, "meta": result.get("meta", {})}
    except Exception as exc:
        return {"data": [], "provenance": [], "source": "fallback", "official": False, "error": str(exc)}


async def _fetch_filings(idx: IDXClient, ticker: str, year: int, period: str) -> dict[str, Any]:
    try:
        result = await idx.financial_reports(ticker=ticker, year=year, period=period, limit=20)
        official = _has_official_idx_provenance(result)
        return {"data": result.get("data", []), "provenance": result.get("provenance", []), "source": "official" if official else "unverified", "official": official, "meta": result.get("meta", {})}
    except Exception as exc:
        return {"data": [], "provenance": [], "source": "fallback", "official": False, "error": str(exc)}


async def _fetch_health(idx: IDXClient) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    start = datetime.now(timezone.utc)
    try:
        health = await idx.health()
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        sources["IDX"] = {"status": health.get("status", "unknown"), "latency_ms": elapsed, "official": True}
    except Exception as exc:
        sources["IDX"] = {"status": "error", "error": str(exc), "official": True}
    sources["BPS"] = {"status": "configured" if bool(__import__("os").environ.get("BPS_API_KEY")) else "missing_api_key", "official": True}
    try:
        from indonesia_data_mcp.ksei import KSEIClient
        ksei = KSEIClient()
        k_start = datetime.now(timezone.utc)
        try:
            k_health = await ksei.health()
            sources["KSEI"] = {"status": k_health.get("status", "unknown"), "latency_ms": int((datetime.now(timezone.utc) - k_start).total_seconds() * 1000), "official": True}
        finally:
            await ksei.close()
    except Exception as exc:
        sources["KSEI"] = {"status": "error", "error": str(exc), "official": True}
    return {"sources": sources, "checked_at": datetime.now(timezone.utc).isoformat()}


async def health_endpoint(request: Request) -> JSONResponse:
    return JSONResponse(await _fetch_health(request.app.state.idx))


async def missions_list(request: Request) -> JSONResponse:
    state_filter = request.query_params.get("state", "").upper()
    missions = request.app.state.stores["missions"]
    if state_filter and state_filter in VALID_STATES:
        missions = [m for m in missions if m["state"] == state_filter]
    return JSONResponse(missions)


async def missions_create(request: Request) -> JSONResponse:
    stores = request.app.state.stores
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "JSON object required"}, status_code=400)
    raw_title = body.get("title", "")
    if not isinstance(raw_title, str):
        return JSONResponse({"error": "title must be a string"}, status_code=400)
    title = raw_title.strip()
    if not title:
        return JSONResponse({"error": "title required"}, status_code=400)
    if len(title) > 120:
        return JSONResponse({"error": "title must be 120 characters or fewer"}, status_code=400)
    raw_ticker = body.get("ticker", "")
    if not isinstance(raw_ticker, str):
        return JSONResponse({"error": "ticker must be a string"}, status_code=400)
    try:
        ticker = _validate_ticker(raw_ticker) if raw_ticker.strip() else ""
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    mission = {"id": f"m-{uuid.uuid4().hex[:6]}", "title": title, "ticker": ticker, "state": "PENDING", "created_at": datetime.now(timezone.utc).isoformat(), "demo": True}
    stores["missions"].insert(0, mission)
    _append_log(stores, "INFO", f"DEMO: Mission created — {title}")
    return JSONResponse(mission, status_code=201)


async def missions_update_state(request: Request) -> JSONResponse:
    stores = request.app.state.stores
    mid = request.path_params["id"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "JSON object required"}, status_code=400)
    raw_state = body.get("state", "")
    if not isinstance(raw_state, str):
        return JSONResponse({"error": "state must be a string"}, status_code=400)
    new_state = raw_state.upper()
    if new_state not in VALID_STATES:
        return JSONResponse({"error": f"state must be one of {', '.join(sorted(VALID_STATES))}"}, status_code=400)
    for m in stores["missions"]:
        if m["id"] == mid:
            m["state"] = new_state
            _append_log(stores, "INFO", f"DEMO: Mission {mid} → {new_state}")
            return JSONResponse(m)
    return JSONResponse({"error": "mission not found"}, status_code=404)


async def watchlist_endpoint(request: Request) -> JSONResponse:
    return JSONResponse(request.app.state.stores["watchlist"])


async def company_endpoint(request: Request) -> JSONResponse:
    try:
        ticker = _validate_ticker(request.path_params["ticker"])
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(await _fetch_company(request.app.state.idx, ticker))


async def announcements_endpoint(request: Request) -> JSONResponse:
    try:
        ticker = _validate_ticker(request.path_params["ticker"])
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(await _fetch_announcements(request.app.state.idx, ticker))


def _filing_query(request: Request) -> tuple[int, str]:
    try:
        year = int(request.query_params.get("year", "2025"))
    except ValueError as exc:
        raise ValueError("year must be an integer") from exc
    current_year = datetime.now(timezone.utc).year
    if year < 2000 or year > current_year + 1:
        raise ValueError(f"year must be between 2000 and {current_year + 1}")
    period = request.query_params.get("period", "audit").strip().lower()
    if period not in {"audit", "q1", "q2", "q3"}:
        raise ValueError("period must be one of audit, q1, q2, q3")
    return year, period


async def filings_endpoint(request: Request) -> JSONResponse:
    try:
        ticker = _validate_ticker(request.path_params["ticker"])
        year, period = _filing_query(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(await _fetch_filings(request.app.state.idx, ticker, year, period))


async def evidence_endpoint(request: Request) -> JSONResponse:
    try:
        ticker = _validate_ticker(request.path_params["ticker"])
        year, period = _filing_query(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    profile, announcements, filings = await asyncio.gather(_fetch_company(request.app.state.idx, ticker), _fetch_announcements(request.app.state.idx, ticker), _fetch_filings(request.app.state.idx, ticker, year, period))
    channels = {"profile": profile, "announcements": announcements, "filings": filings}
    return JSONResponse({"ticker": ticker, "channels": channels, "official_only": all(item.get("official") is True for item in channels.values()), "generated_at": datetime.now(timezone.utc).isoformat(), "warnings": ["Workflow missions and agent operations are demo state.", "No licensed official market prices or investment recommendations are provided.", "Filing records are not canonical cross-company normalization."]})


async def operations_endpoint(request: Request) -> JSONResponse:
    return JSONResponse(request.app.state.stores["operations"])


async def log_endpoint(request: Request) -> JSONResponse:
    return JSONResponse(request.app.state.stores["log"])


async def index_page(request: Request) -> Response:
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return Response(content=index_path.read_text(encoding="utf-8"), media_type="text/html")
    return Response(content="<h1>IDX Research Desk</h1><p>Static files are unavailable.</p>", media_type="text/html")


def _append_log(stores: dict[str, Any], level: str, msg: str) -> None:
    stores["log"].append({"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg})
    if len(stores["log"]) > 500:
        stores["log"] = stores["log"][-200:]


def create_app() -> Starlette:
    async def empty_icon(request: Request) -> Response:
        return Response(status_code=204)
    routes = [Route("/", index_page), Route("/favicon.ico", empty_icon), Route("/api/health", health_endpoint), Route("/api/missions", missions_list, methods=["GET"]), Route("/api/missions", missions_create, methods=["POST"]), Route("/api/missions/{id}/state", missions_update_state, methods=["PATCH"]), Route("/api/watchlist", watchlist_endpoint), Route("/api/company/{ticker}", company_endpoint), Route("/api/announcements/{ticker}", announcements_endpoint), Route("/api/filings/{ticker}", filings_endpoint), Route("/api/evidence/{ticker}", evidence_endpoint), Route("/api/operations", operations_endpoint), Route("/api/log", log_endpoint), Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static")]
    @asynccontextmanager
    async def lifespan(app: Starlette):
        app.state.idx = IDXClient()
        app.state.stores = _make_stores()
        yield
        await app.state.idx.close()
    return Starlette(routes=routes, lifespan=lifespan)


app = create_app()
