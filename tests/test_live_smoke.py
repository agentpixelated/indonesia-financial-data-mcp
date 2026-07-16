"""Opt-in live source tests.

Run with: RUN_LIVE=1 pytest tests/test_live_smoke.py -q
"""

import os
from datetime import datetime

import pytest

from indonesia_data_mcp.idx import IDXClient
from indonesia_data_mcp.ksei import KSEIClient


pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE") != "1", reason="live tests are opt-in")


@pytest.mark.asyncio
async def test_live_idx_company_and_financial_report():
    client = IDXClient()
    try:
        companies = await client.list_companies(limit=2)
        report = await client.financial_reports("BBCA", 2026, "TW1")
    finally:
        await client.close()

    assert companies["meta"]["total"] > 900
    assert all(row["ticker"] for row in companies["data"])
    assert report["data"][0]["ticker"] == "BBCA"
    assert {a["format"] for a in report["data"][0]["attachments"]} >= {"xlsx", "pdf", "zip"}
    assert all(source["official"] for source in companies["provenance"] + report["provenance"])


@pytest.mark.asyncio
async def test_live_ksei_sid_growth():
    client = KSEIClient()
    try:
        result = await client.sid_growth(
            month_year="June 2026", metric="Jumlah Investor Pasar Modal"
        )
    finally:
        await client.close()

    assert result["data"]
    assert result["data"][-1]["value"] > 0
    assert result["provenance"][0]["official"] is True
