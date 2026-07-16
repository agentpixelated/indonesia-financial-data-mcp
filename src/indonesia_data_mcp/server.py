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


server = Server("indonesia-financial-data")
_idx = IDXClient()
_bps = BPSClient(api_key=os.getenv("BPS_API_KEY", ""))
_ksei = KSEIClient()


async def _idx_list_companies(**kwargs: Any) -> dict[str, Any]:
    return await _idx.list_companies(**kwargs)


async def _idx_company_profile(**kwargs: Any) -> dict[str, Any]:
    return await _idx.company_profile(**kwargs)


async def _idx_company_announcements(**kwargs: Any) -> dict[str, Any]:
    return await _idx.announcements(**kwargs)


async def _idx_financial_reports(**kwargs: Any) -> dict[str, Any]:
    return await _idx.financial_reports(**kwargs)


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
    return {"data": checks, "provenance": []}


TOOL_HANDLERS: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {
    "idx_list_companies": _idx_list_companies,
    "idx_company_profile": _idx_company_profile,
    "idx_company_announcements": _idx_company_announcements,
    "idx_financial_reports": _idx_financial_reports,
    "bps_list_subjects": _bps_list_subjects,
    "bps_list_variables": _bps_list_variables,
    "bps_get_data": _bps_get_data,
    "ksei_sid_growth": _ksei_sid_growth,
    "ksei_investor_demographics": _ksei_investor_demographics,
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
        name="source_health",
        description="Check first-party source availability and BPS credential readiness.",
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
