import json

import pytest

from indonesia_data_mcp import server


OFFICIAL_TOOLS = {
    "idx_list_companies",
    "idx_company_profile",
    "idx_company_announcements",
    "idx_financial_reports",
    "idx_filing_facts",
    "bps_list_subjects",
    "bps_list_variables",
    "bps_get_data",
    "ksei_sid_growth",
    "ksei_investor_demographics",
    "source_health",
}

# Market tools delegate to the MIT-licensed fzn0x/idx CLI (see
# THIRD_PARTY_NOTICES.md). They are optional, non-official, and every
# description must say so — that labelling is the contract this test guards.
MARKET_TOOLS = {
    "market_quote",
    "market_history",
    "market_fundamental",
    "market_technical",
    "market_screen",
    "market_foreign",
    "market_overview",
    "market_indices",
    "ownership_holders",
}


@pytest.mark.asyncio
async def test_server_lists_official_and_labelled_market_tools():
    tools = await server.handle_list_tools()
    names = {tool.name for tool in tools}

    assert names == OFFICIAL_TOOLS | MARKET_TOOLS
    for tool in tools:
        if tool.name in MARKET_TOOLS:
            assert "official=false" in tool.description
            assert "fzn0x/idx" in tool.description
        elif tool.name != "source_health":
            assert "Yahoo" not in tool.description


@pytest.mark.asyncio
async def test_server_routes_filing_facts_with_defaults(monkeypatch):
    expected = {"data": {"facts": []}, "provenance": [], "meta": {"total": 0}}

    async def fake_filing_facts(**kwargs):
        assert kwargs == {
            "ticker": "BBCA",
            "year": 2025,
            "period": "audit",
            "concept": "",
            "limit": 500,
            "offset": 0,
        }
        return expected

    monkeypatch.setitem(server.TOOL_HANDLERS, "idx_filing_facts", fake_filing_facts)
    content = await server.handle_call_tool(
        "idx_filing_facts", {"ticker": "BBCA", "year": 2025}
    )

    assert json.loads(content[0].text) == expected


@pytest.mark.asyncio
async def test_server_routes_tool_and_returns_json(monkeypatch):
    expected = {"data": [{"ticker": "BBCA"}], "provenance": []}

    async def fake_list_companies(**kwargs):
        assert kwargs == {"limit": 3, "offset": 0}
        return expected

    monkeypatch.setitem(server.TOOL_HANDLERS, "idx_list_companies", fake_list_companies)
    content = await server.handle_call_tool("idx_list_companies", {"limit": 3})

    assert json.loads(content[0].text) == expected


@pytest.mark.asyncio
async def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError, match="Unknown tool"):
        await server.handle_call_tool("yahoo_price", {})
