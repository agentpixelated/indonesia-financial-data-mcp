import httpx
import pytest

from indonesia_data_mcp.idx import IDXClient


@pytest.mark.asyncio
async def test_idx_client_recovers_when_cloudflare_blocks_session_home_once():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/":
            return httpx.Response(403, text="Attention Required! | Cloudflare")
        if request.url.path == "/en":
            return httpx.Response(200, text="home", headers={"set-cookie": "idx-session=ok"})
        return httpx.Response(200, json={"recordsTotal": 0, "data": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await IDXClient(http=http).list_companies(limit=1)

    assert calls.count("/") == 3
    assert "/en" in calls
    assert result["meta"]["total"] == 0
