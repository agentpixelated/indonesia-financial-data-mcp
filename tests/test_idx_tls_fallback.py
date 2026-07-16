import httpx
import pytest

from indonesia_data_mcp.idx import IDXClient


@pytest.mark.asyncio
async def test_idx_falls_back_to_browser_tls_transport_after_cloudflare_block():
    def blocked(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Attention Required! | Cloudflare")

    calls = []

    async def browser_get_json(url, headers):
        calls.append((url, headers))
        return {"recordsTotal": 0, "data": []}

    async with httpx.AsyncClient(transport=httpx.MockTransport(blocked)) as http:
        client = IDXClient(http=http, browser_get_json=browser_get_json)
        result = await client.list_companies(limit=1)

    assert calls[0][0].startswith(
        "https://www.idx.co.id/primary/ListedCompany/GetCompanyProfiles"
    )
    assert result["meta"]["total"] == 0
    assert result["warnings"] == ["IDX required browser-compatible TLS transport"]
