import hashlib
import io
import zipfile

import httpx
import pytest

from indonesia_data_mcp.filing import parse_instance_zip
from indonesia_data_mcp.idx import IDXClient


SAMPLE_XBRL = b'''<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
    xmlns:idx-cor="http://www.idx.co.id/xbrl/taxonomy/2024-04-30/cor">
  <xbrli:context id="CurrentYearInstant">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.idx.co.id/xbrl">bbca_user</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:context id="CurrentYearDuration_Parent">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.idx.co.id/xbrl">bbca_user</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2025-01-01</xbrli:startDate>
      <xbrli:endDate>2025-12-31</xbrli:endDate>
    </xbrli:period>
    <xbrli:scenario>
      <xbrldi:explicitMember dimension="idx-cor:ConsolidationAxis">idx-cor:ParentEntityMember</xbrldi:explicitMember>
    </xbrli:scenario>
  </xbrli:context>
  <xbrli:unit id="IDR"><xbrli:measure>iso4217:IDR</xbrli:measure></xbrli:unit>
  <idx-cor:EntityName contextRef="CurrentYearInstant">PT Bank Central Asia Tbk.</idx-cor:EntityName>
  <idx-cor:Assets contextRef="CurrentYearInstant" unitRef="IDR" decimals="-6">1586828536000000</idx-cor:Assets>
  <idx-cor:ProfitLoss contextRef="CurrentYearDuration_Parent" unitRef="IDR" decimals="-6">57563093000000</idx-cor:ProfitLoss>
  <idx-cor:RestrictedFunds contextRef="CurrentYearInstant" unitRef="IDR" xsi:nil="true"/>
</xbrli:xbrl>
'''


def instance_zip(xml: bytes = SAMPLE_XBRL, *, member: str = "instance.xbrl") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, xml)
    return buffer.getvalue()


def report_response(download_url: str) -> dict:
    return {
        "data": [
            {
                "ticker": "BBCA",
                "name": "PT Bank Central Asia Tbk.",
                "year": 2025,
                "period": "Audit",
                "attachments": [
                    {
                        "id": "attachment-one",
                        "filename": "instance.zip",
                        "format": "zip",
                        "size_bytes": 123,
                        "modified_at": "2026-01-27T16:39:15.333",
                        "download_url": download_url,
                    }
                ],
            }
        ],
        "provenance": [
            {
                "provider": "IDX",
                "source_url": "https://www.idx.co.id/primary/ListedCompany/GetFinancialReport?kodeEmiten=BBCA",
                "retrieved_at": "2026-07-22T00:00:00+00:00",
                "official": True,
                "source_format": "json",
            }
        ],
    }


def test_parse_instance_zip_preserves_raw_xbrl_semantics():
    result = parse_instance_zip(instance_zip())

    assert result["total"] == 4
    facts = {fact["concept"]: fact for fact in result["facts"]}

    assets = facts["Assets"]
    assert assets["concept_qname"] == "{http://www.idx.co.id/xbrl/taxonomy/2024-04-30/cor}Assets"
    assert assets["value_type"] == "number"
    assert assets["raw_value"] == "1586828536000000"
    assert assets["numeric_value"] == "1586828536000000"
    assert assets["decimals"] == "-6"
    assert assets["unit"] == {"id": "IDR", "measures": ["iso4217:IDR"]}
    assert assets["context"]["period"] == {"type": "instant", "instant": "2025-12-31"}
    assert assets["context"]["entity"]["identifier"] == "bbca_user"

    profit = facts["ProfitLoss"]
    assert profit["context"]["period"] == {
        "type": "duration",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
    }
    assert profit["context"]["dimensions"] == [
        {"axis": "idx-cor:ConsolidationAxis", "member": "idx-cor:ParentEntityMember"}
    ]

    assert facts["EntityName"]["value_type"] == "text"
    assert facts["RestrictedFunds"]["value_type"] == "nil"
    assert facts["RestrictedFunds"]["raw_value"] is None


def test_parse_instance_zip_filters_and_paginates_by_concept():
    result = parse_instance_zip(instance_zip(), concept="profit", limit=1, offset=0)

    assert result["total"] == 1
    assert [fact["concept"] for fact in result["facts"]] == ["ProfitLoss"]
    assert result["offset"] == 0
    assert result["limit"] == 1


def test_parse_instance_zip_rejects_unsafe_or_ambiguous_archives():
    with pytest.raises(ValueError, match="unsafe ZIP member"):
        parse_instance_zip(instance_zip(member="../instance.xbrl"))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("one/instance.xbrl", SAMPLE_XBRL)
        archive.writestr("two/instance.xbrl", SAMPLE_XBRL)
    with pytest.raises(ValueError, match="exactly one instance.xbrl"):
        parse_instance_zip(buffer.getvalue())


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_parse_instance_zip_rejects_xml_entities_in_any_encoding(encoding):
    xml = '''<?xml version="1.0"?><!DOCTYPE x [<!ENTITY secret "expanded">]>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">&secret;</xbrli:xbrl>'''.encode(
        encoding
    )
    with pytest.raises(ValueError, match="Unsafe or invalid XBRL XML"):
        parse_instance_zip(instance_zip(xml))


@pytest.mark.asyncio
async def test_filing_facts_resolves_downloads_and_cites_official_instance(monkeypatch):
    payload = instance_zip()
    downloads = []

    async def fake_reports(*args, **kwargs):
        return report_response(
            "https://www.idx.co.id/reports//Laporan Keuangan/BBCA/instance.zip"
        )

    async def fake_download(url, headers, max_bytes):
        downloads.append((url, headers, max_bytes))
        return payload

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))) as http:
        client = IDXClient(http=http, browser_get_bytes=fake_download)
        monkeypatch.setattr(client, "financial_reports", fake_reports)
        result = await client.filing_facts(
            "bbca", 2025, "audit", concept="assets", limit=10
        )

    assert "%20" in downloads[0][0]
    assert downloads[0][0].startswith("https://www.idx.co.id/")
    assert downloads[0][1]["Referer"] == "https://www.idx.co.id/"
    assert result["data"]["filing"]["ticker"] == "BBCA"
    assert result["data"]["attachment"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert result["data"]["attachment"]["downloaded_size_bytes"] == len(payload)
    assert [fact["concept"] for fact in result["data"]["facts"]] == ["Assets"]
    assert result["meta"]["total"] == 1
    assert [item["source_format"] for item in result["provenance"]] == ["json", "xbrl_zip"]
    assert "not canonical normalization" in result["warnings"][0]


@pytest.mark.asyncio
async def test_filing_facts_rejects_non_idx_attachment_before_download(monkeypatch):
    called = False

    async def fake_reports(*args, **kwargs):
        return report_response("https://evil.example/instance.zip")

    async def fake_download(url, headers, max_bytes):
        nonlocal called
        called = True
        return instance_zip()

    client = IDXClient(browser_get_bytes=fake_download)
    monkeypatch.setattr(client, "financial_reports", fake_reports)

    with pytest.raises(ValueError, match="official IDX HTTPS URL"):
        await client.filing_facts("BBCA", 2025)
    assert called is False
    await client.close()


@pytest.mark.asyncio
async def test_filing_facts_rejects_oversized_injected_download(monkeypatch):
    async def fake_reports(*args, **kwargs):
        return report_response("https://www.idx.co.id/reports/instance.zip")

    async def fake_download(url, headers, max_bytes):
        return b"x" * (max_bytes + 1)

    client = IDXClient(browser_get_bytes=fake_download)
    monkeypatch.setattr(client, "financial_reports", fake_reports)

    with pytest.raises(RuntimeError, match="exceeds maximum size"):
        await client.filing_facts("BBCA", 2025)
    await client.close()
