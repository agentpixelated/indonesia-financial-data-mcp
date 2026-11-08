"""stdio MCP server exposing official Indonesian financial data."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .bps import BPSClient
from .idx import IDXClient
from .ksei import KSEIClient
from .market import MarketClient


server = Server("indonesia-financial-data")
_idx = IDXClient()
_bps = BPSClient(api_key=os.getenv("BPS_API_KEY", ""))
_ksei = KSEIClient()
_market = MarketClient()


async def _idx_list_companies(**kwargs: Any) -> dict[str, Any]:
    return await _idx.list_companies(**kwargs)


async def _idx_company_profile(**kwargs: Any) -> dict[str, Any]:
    return await _idx.company_profile(**kwargs)


async def _idx_company_announcements(**kwargs: Any) -> dict[str, Any]:
    return await _idx.announcements(**kwargs)


async def _idx_financial_reports(**kwargs: Any) -> dict[str, Any]:
    return await _idx.financial_reports(**kwargs)


async def _idx_filing_facts(**kwargs: Any) -> dict[str, Any]:
    return await _idx.filing_facts(**kwargs)


async def _bps_list_subjects(**kwargs: Any) -> dict[str, Any]:
    return await _bps.list_subjects(**kwargs)


async def _bps_list_variables(**kwargs: Any) -> dict[str, Any]:
    return await _bps.list_variables(**kwargs)


async def _bps_get_data(**kwargs: Any) -> dict[str, Any]:
    return await _bps.get_data(**kwargs)


async def _ksei_sid_growth(**kwargs: Any) -> dict[str, Any]:
    return await _ksei.sid_growth(**kwargs)


async def _ksei_investor_demographics(**kwargs: Any) -> dict[str, Any]:
    return await _ksei.investor_demographics(**kwargs)


async def _market_quote(**kwargs: Any) -> dict[str, Any]:
    return await _market.quote(**kwargs)


async def _market_history(**kwargs: Any) -> dict[str, Any]:
    return await _market.history(**kwargs)


async def _market_fundamental(**kwargs: Any) -> dict[str, Any]:
    return await _market.fundamental(**kwargs)


async def _market_technical(**kwargs: Any) -> dict[str, Any]:
    return await _market.technical(**kwargs)


async def _market_screen(**kwargs: Any) -> dict[str, Any]:
    return await _market.screen(**kwargs)


async def _market_foreign(**kwargs: Any) -> dict[str, Any]:
    return await _market.foreign(**kwargs)


async def _market_overview(**kwargs: Any) -> dict[str, Any]:
    return await _market.overview(**kwargs)


async def _market_indices(**kwargs: Any) -> dict[str, Any]:
    return await _market.indices(**kwargs)


async def _ownership_holders(**kwargs: Any) -> dict[str, Any]:
    return await _market.ownership_ticker(**kwargs)


async def _source_health(**_: Any) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for name, operation in {
        "IDX": lambda: _idx.list_companies(limit=1),
        "KSEI": lambda: _ksei.sid_growth(
            month_year=datetime.now().strftime("%B %Y"),
            metric="Jumlah Investor Pasar Modal",
        ),
    }.items():
        started = datetime.now(timezone.utc)
        try:
            result = await operation()
            checks[name] = {
                "status": "ok",
                "official": True,
                "provenance": result.get("provenance", []),
                "latency_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
            }
        except Exception as exc:
            checks[name] = {"status": "error", "official": True, "error": str(exc)}
    checks["BPS"] = {
        "status": "configured" if _bps.api_key else "missing_api_key",
        "official": True,
        "documentation": "https://webapi.bps.go.id/documentation/",
    }
    checks["fzn_idx_market"] = {
        "status": "available" if _market.available() else "binary_missing",
        "official": False,
        "binary": _market.binary,
        "upstream": "https://github.com/fzn0x/idx",
        "install": "npm install -g ihsg-cli",
    }
    return {"data": checks, "provenance": []}


TOOL_HANDLERS: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {
    "idx_list_companies": _idx_list_companies,
    "idx_company_profile": _idx_company_profile,
    "idx_company_announcements": _idx_company_announcements,
    "idx_financial_reports": _idx_financial_reports,
    "idx_filing_facts": _idx_filing_facts,
    "bps_list_subjects": _bps_list_subjects,
    "bps_list_variables": _bps_list_variables,
    "bps_get_data": _bps_get_data,
    "ksei_sid_growth": _ksei_sid_growth,
    "ksei_investor_demographics": _ksei_investor_demographics,
    "market_quote": _market_quote,
    "market_history": _market_history,
    "market_fundamental": _market_fundamental,
    "market_technical": _market_technical,
    "market_screen": _market_screen,
    "market_foreign": _market_foreign,
    "market_overview": _market_overview,
    "market_indices": _market_indices,
    "ownership_holders": _ownership_holders,
    "source_health": _source_health,
}


def _object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


TOOLS = [
    Tool(
        name="idx_list_companies",
        description="List IDX issuers from the official IDX endpoint with sector, industry, listing date, and source citation.",
        inputSchema=_object(
            {
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            }
        ),
    ),
    Tool(
        name="idx_company_profile",
        description="Get an official IDX issuer profile, management, and disclosed shareholder snapshot.",
        inputSchema=_object(
            {
                "ticker": {"type": "string", "pattern": "^[A-Za-z0-9]{4,8}$"},
                "language": {"type": "string", "enum": ["id-id", "en-us"], "default": "id-id"},
            },
            ["ticker"],
        ),
    ),
    Tool(
        name="idx_company_announcements",
        description="Search official IDX issuer announcements and return direct attachment URLs with citations.",
        inputSchema=_object(
            {
                "ticker": {"type": "string", "default": ""},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "date_from": {"type": "string", "pattern": "^$|^[0-9]{8}$", "default": ""},
                "date_to": {"type": "string", "pattern": "^$|^[0-9]{8}$", "default": ""},
                "language": {"type": "string", "enum": ["id", "en"], "default": "id"},
            }
        ),
    ),
    Tool(
        name="idx_financial_reports",
        description="Find official IDX financial-report attachments (XLSX, PDF, XBRL ZIP, inline-XBRL ZIP).",
        inputSchema=_object(
            {
                "ticker": {"type": "string", "pattern": "^[A-Za-z0-9]{4,8}$"},
                "year": {"type": "integer", "minimum": 2000, "maximum": 2100},
                "period": {"type": "string", "enum": ["TW1", "TW2", "TW3", "audit"], "default": "audit"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            },
            ["ticker", "year"],
        ),
    ),
    Tool(
        name="idx_filing_facts",
        description=(
            "Query raw facts from an official IDX instance.zip XBRL filing, with contexts, units, "
            "attachment SHA-256, and citations. Facts are not canonical normalization."
        ),
        inputSchema=_object(
            {
                "ticker": {"type": "string", "pattern": "^[A-Za-z0-9]{4,8}$"},
                "year": {"type": "integer", "minimum": 2000, "maximum": 2100},
                "period": {"type": "string", "enum": ["TW1", "TW2", "TW3", "audit"], "default": "audit"},
                "concept": {
                    "type": "string",
                    "default": "",
                    "description": "Case-insensitive substring filter for the XBRL concept name or QName.",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            },
            ["ticker", "year"],
        ),
    ),
    Tool(
        name="bps_list_subjects",
        description="List official BPS statistical subjects. Requires BPS_API_KEY from the BPS developer portal.",
        inputSchema=_object(
            {
                "domain": {"type": "integer", "minimum": 0, "maximum": 9999, "default": 0},
                "language": {"type": "string", "enum": ["ind", "eng"], "default": "ind"},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "subject_category": {"type": ["integer", "null"], "default": None},
            }
        ),
    ),
    Tool(
        name="bps_list_variables",
        description="List official BPS variables for a subject and domain.",
        inputSchema=_object(
            {
                "subject_id": {"type": "integer", "minimum": 1},
                "domain": {"type": "integer", "minimum": 0, "maximum": 9999, "default": 0},
                "language": {"type": "string", "enum": ["ind", "eng"], "default": "ind"},
                "page": {"type": "integer", "minimum": 1, "default": 1},
            },
            ["subject_id"],
        ),
    ),
    Tool(
        name="bps_get_data",
        description="Read an official BPS dynamic-table series by variable and period IDs.",
        inputSchema=_object(
            {
                "variable_id": {"type": "integer", "minimum": 1},
                "period_ids": {"type": "string"},
                "domain": {"type": "integer", "minimum": 0, "maximum": 9999, "default": 0},
                "language": {"type": "string", "enum": ["ind", "eng"], "default": "ind"},
                "derived_variable_id": {"type": ["integer", "null"], "default": None},
                "vertical_variable_id": {"type": ["integer", "null"], "default": None},
                "derived_period_ids": {"type": ["string", "null"], "default": None},
            },
            ["variable_id", "period_ids"],
        ),
    ),
    Tool(
        name="ksei_sid_growth",
        description="Get official KSEI investor-count growth series by month and metric.",
        inputSchema=_object(
            {"month_year": {"type": "string"}, "metric": {"type": "string"}},
            ["month_year", "metric"],
        ),
    ),
    Tool(
        name="ksei_investor_demographics",
        description="Get official KSEI investor demographics by month and dimension.",
        inputSchema=_object(
            {
                "month_year": {"type": "string"},
                "dimension": {"type": "string", "enum": ["gender", "age", "education", "job", "income"]},
            },
            ["month_year", "dimension"],
        ),
    ),
    Tool(
        name="market_quote",
        description=(
            "Delayed price quote for one or more IDX tickers (comma-separated, e.g. 'BBCA,BBRI'). "
            "NON-OFFICIAL market data via the MIT-licensed fzn0x/idx CLI (Yahoo Finance / MSN Money); "
            "provenance is labelled official=false. Requires the idx binary (npm install -g ihsg-cli)."
        ),
        inputSchema=_object(
            {"symbols": {"type": "string", "description": "Comma-separated tickers, .JK optional."}},
            ["symbols"],
        ),
    ),
    Tool(
        name="market_history",
        description="Delayed OHLCV history for one ticker via fzn0x/idx (non-official, official=false).",
        inputSchema=_object(
            {
                "symbol": {"type": "string", "pattern": "^[A-Za-z0-9.]{4,10}$"},
                "period": {"type": "string", "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"], "default": "1y"},
                "interval": {"type": "string", "enum": ["1m", "2m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"], "default": "1d"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 30},
            },
            ["symbol"],
        ),
    ),
    Tool(
        name="market_fundamental",
        description=(
            "Fundamental ratios (P/E, P/B, PEG, EV/EBITDA, ROE, margins, leverage, dividend) with the "
            "upstream rule-based verdict, via fzn0x/idx (non-official, official=false). The verdict is "
            "the upstream tool's rule output, not this project's recommendation."
        ),
        inputSchema=_object({"symbol": {"type": "string", "pattern": "^[A-Za-z0-9.]{4,10}$"}}, ["symbol"]),
    ),
    Tool(
        name="market_technical",
        description="Technical indicators (RSI, MACD, SMA/EMA, Bollinger, ATR) via fzn0x/idx (non-official, official=false).",
        inputSchema=_object(
            {
                "symbol": {"type": "string", "pattern": "^[A-Za-z0-9.]{4,10}$"},
                "period": {"type": "string", "enum": ["3mo", "6mo", "1y", "2y", "5y"], "default": "1y"},
            },
            ["symbol"],
        ),
    ),
    Tool(
        name="market_screen",
        description=(
            "Screen ~950 IDX tickers via fzn0x/idx (non-official, official=false). Use a preset "
            "(top-performers, high-dividend, low-pe, 52w-high, 52w-low, high-volume, large-cap) or a "
            "filter expression like 'pe<15,roe>15,sector=financial'."
        ),
        inputSchema=_object(
            {
                "preset": {"type": "string", "default": ""},
                "filter_expr": {"type": "string", "default": ""},
                "sort": {"type": "string", "default": ""},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            }
        ),
    ),
    Tool(
        name="market_foreign",
        description="Foreign buy/sell per session for a ticker from idx.co.id summaries via fzn0x/idx (non-official wrapper, official=false).",
        inputSchema=_object(
            {
                "symbol": {"type": "string", "pattern": "^[A-Za-z0-9.]{4,10}$"},
                "days": {"type": "integer", "minimum": 1, "maximum": 120, "default": 20},
            },
            ["symbol"],
        ),
    ),
    Tool(
        name="market_overview",
        description="IHSG overview: index, breadth, turnover, top gainers/losers via fzn0x/idx (non-official, official=false).",
        inputSchema=_object({"top": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}}),
    ),
    Tool(
        name="market_indices",
        description="All IDX indices (IHSG, LQ45, IDX30, sector/thematic) for the latest session via fzn0x/idx (non-official, official=false).",
        inputSchema=_object({}),
    ),
    Tool(
        name="ownership_holders",
        description=(
            "Holders above 1% of a ticker from KSEI's monthly register, via fzn0x/idx's local ownership "
            "database (requires a prior `idx ownership sync` on the host; non-official wrapper, official=false)."
        ),
        inputSchema=_object({"symbol": {"type": "string", "pattern": "^[A-Za-z0-9.]{4,10}$"}}, ["symbol"]),
    ),
    Tool(
        name="source_health",
        description="Check first-party source availability, BPS credential readiness, and the fzn0x/idx market backend.",
        inputSchema=_object({}),
    ),
]


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name}")
    supplied = dict(arguments or {})
    tool = next(item for item in TOOLS if item.name == name)
    for key, definition in tool.inputSchema.get("properties", {}).items():
        if key not in supplied and "default" in definition:
            supplied[key] = definition["default"]
    result = await handler(**supplied)
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
