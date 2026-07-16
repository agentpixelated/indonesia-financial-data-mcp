from indonesia_data_mcp.models import Provenance, envelope


def test_envelope_requires_official_https_source():
    source = Provenance(
        provider="IDX",
        source_url="https://www.idx.co.id/primary/ListedCompany/GetCompanyProfiles",
        retrieved_at="2026-07-16T00:00:00+00:00",
        official=True,
    )

    result = envelope({"ticker": "BBCA"}, source)

    assert result["data"] == {"ticker": "BBCA"}
    assert result["provenance"][0]["provider"] == "IDX"
    assert result["provenance"][0]["official"] is True
    assert result["provenance"][0]["source_url"].startswith("https://")


def test_envelope_does_not_hide_partial_data():
    source = Provenance(
        provider="IDX",
        source_url="https://www.idx.co.id/primary/ListedCompany/GetFinancialReport",
        retrieved_at="2026-07-16T00:00:00+00:00",
        official=True,
    )

    result = envelope([], source, warnings=["No matching report"])

    assert result["data"] == []
    assert result["warnings"] == ["No matching report"]
