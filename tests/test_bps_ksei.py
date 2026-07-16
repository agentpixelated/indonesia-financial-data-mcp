import httpx
import pytest

from indonesia_data_mcp.bps import BPSClient
from indonesia_data_mcp.ksei import KSEIClient


@pytest.mark.asyncio
async def test_bps_refuses_network_without_api_key():
    client = BPSClient(api_key="", http=httpx.AsyncClient())
    with pytest.raises(RuntimeError, match="BPS_API_KEY"):
        await client.list_subjects()


@pytest.mark.asyncio
async def test_bps_passes_key_to_official_api_but_redacts_provenance():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "status": "OK",
                "data-availability": "available",
                "data": [
                    {"page": 1, "pages": 1, "total": 1},
                    [{"sub_id": 1, "title": "Penduduk", "subcat_id": 1}],
                ],
            },
        )

    credential = "fixture-value"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await BPSClient(api_key=credential, http=http).list_subjects()

    assert observed["params"]["key"] == credential
    assert credential not in result["provenance"][0]["source_url"]
    assert result["data"][0]["title"] == "Penduduk"
    assert result["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_ksei_sid_growth_returns_official_series():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "application/json"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "rn": 5,
                        "month": "June 2026",
                        "asset_local": 28961144,
                        "type": "Jumlah Investor Pasar Modal",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await KSEIClient(http=http).sid_growth(
            month_year="June 2026", metric="Jumlah Investor Pasar Modal"
        )

    assert result["data"][0]["value"] == 28961144
    assert result["data"][0]["period"] == "June 2026"
    assert result["provenance"][0]["provider"] == "KSEI"


@pytest.mark.asyncio
async def test_ksei_rejects_unexpected_html():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>blocked</html>", headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(RuntimeError, match="Expected JSON"):
            await KSEIClient(http=http).sid_growth(
                month_year="June 2026", metric="Jumlah Investor Pasar Modal"
            )
