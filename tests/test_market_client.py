"""Unit tests for the fzn0x/idx market backend wrapper (no network, no binary)."""

import json

import pytest

from indonesia_data_mcp.market import MarketClient, MarketUnavailable


def make_client(payload, code=0, err=""):
    async def fake_runner(argv):
        assert argv[1:3] == ["-o", "json"]
        return code, json.dumps(payload) if not isinstance(payload, str) else payload, err

    client = MarketClient(binary="/bin/true", runner=fake_runner)
    return client


@pytest.mark.asyncio
async def test_quote_wraps_with_unofficial_provenance():
    client = make_client(
        {
            "schema": "idx.quotes.v1",
            "provider": "yahoo",
            "fetched_at": "2026-11-08T00:00:00Z",
            "cached": False,
            "stale": False,
            "warnings": ["delayed"],
            "data": [{"symbol": "BBCA", "price": 5200.0}],
        }
    )
    result = await client.quote("BBCA")
    assert result["data"][0]["symbol"] == "BBCA"
    prov = result["provenance"][0]
    assert prov["official"] is False
    assert "fzn0x/idx" in prov["provider"]
    assert prov["source_url"] == "https://github.com/fzn0x/idx"
    assert result["warnings"] == ["delayed"]
    assert result["meta"]["upstream_schema"] == "idx.quotes.v1"


@pytest.mark.asyncio
async def test_upstream_error_is_surfaced():
    client = make_client("", code=3, err='{"error":{"code":"network","message":"boom"},"exit_code":3}')
    with pytest.raises(MarketUnavailable, match="boom"):
        await client.quote("BBCA")


@pytest.mark.asyncio
async def test_missing_binary_message_names_install():
    client = MarketClient(binary="/nonexistent/idx")
    with pytest.raises(MarketUnavailable, match="ihsg-cli"):
        await client.quote("BBCA")
