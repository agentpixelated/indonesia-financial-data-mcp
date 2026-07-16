import httpx
import pytest

from indonesia_data_mcp.idx import IDXClient


@pytest.mark.asyncio
async def test_list_companies_normalizes_idx_payload_and_provenance():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/id":
            return httpx.Response(200, text="home", headers={"set-cookie": "idx-session=ok"})
        return httpx.Response(
            200,
            json={
                "recordsTotal": 1,
                "data": [
                    {
                        "KodeEmiten": "BBCA",
                        "NamaEmiten": "PT Bank Central Asia Tbk.",
                        "TanggalPencatatan": "2000-05-31T00:00:00",
                        "Sektor": "Keuangan",
                        "SubSektor": "Bank",
                        "Industri": "Bank",
                        "SubIndustri": "Bank",
                        "PapanPencatatan": "Utama",
                        "KegiatanUsahaUtama": "Jasa Perbankan",
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        result = await IDXClient(http=http).list_companies(limit=10)

    assert result["data"][0]["ticker"] == "BBCA"
    assert result["data"][0]["sector"] == "Keuangan"
    assert result["meta"]["total"] == 1
    assert result["provenance"][0]["provider"] == "IDX"
    assert any(url.endswith("/") for url in calls)


@pytest.mark.asyncio
async def test_financial_reports_exposes_all_official_attachments():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/id":
            return httpx.Response(200, text="home")
        return httpx.Response(
            200,
            json={
                "ResultCount": 1,
                "Results": [
                    {
                        "KodeEmiten": "BBCA",
                        "NamaEmiten": "PT Bank Central Asia Tbk.",
                        "Report_Year": "2026",
                        "Report_Period": "TW1",
                        "Attachments": [
                            {
                                "File_ID": "one",
                                "File_Name": "FinancialStatement-2026-I-BBCA.xlsx",
                                "File_Path": "/reports/FinancialStatement-2026-I-BBCA.xlsx",
                                "File_Size": 123,
                                "File_Type": ".xlsx",
                                "File_Modified": "2026-04-23T17:06:59.06",
                            },
                            {
                                "File_ID": "two",
                                "File_Name": "inlineXBRL.zip",
                                "File_Path": "/reports/inlineXBRL.zip",
                                "File_Size": 456,
                                "File_Type": ".zip",
                                "File_Modified": "2026-04-23T17:06:59.06",
                            },
                        ],
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await IDXClient(http=http).financial_reports("bbca", 2026, "tw1")

    report = result["data"][0]
    assert report["ticker"] == "BBCA"
    assert {item["format"] for item in report["attachments"]} == {"xlsx", "zip"}
    assert all(item["download_url"].startswith("https://www.idx.co.id/") for item in report["attachments"])
    assert result["provenance"][0]["source_url"].startswith(
        "https://www.idx.co.id/primary/ListedCompany/GetFinancialReport"
    )


def test_idx_rejects_invalid_ticker_and_period():
    client = IDXClient(http=httpx.AsyncClient())
    with pytest.raises(ValueError):
        client._ticker("BBCA.JK")
    with pytest.raises(ValueError):
        client._period("Q4")
