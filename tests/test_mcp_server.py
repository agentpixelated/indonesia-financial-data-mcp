import json

import pytest

from indonesia_data_mcp import server


@pytest.mark.asyncio
async def test_server_lists_first_party_tools_only():
    tools = await server.handle_list_tools()
    names = {tool.name for tool in tools}

    assert names == {
        "idx_list_companies",
        "idx_company_profile",
        "idx_company_announcements",
        "idx_financial_reports",
        "bps_list_subjects",
        "bps_list_variables",
        "bps_get_data",
        "ksei_sid_growth",
        "ksei_investor_demographics",
        "source_health",
    }
    assert all("Yahoo" not in tool.description for tool in tools)


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
