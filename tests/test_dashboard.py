"""Tests for the dashboard Starlette API and static serving."""

import json

import pytest

# Import will fail until we implement the app → TDD red phase.
from dashboard.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    """ASGI test client — use httpx + starlette's TestClient."""
    from starlette.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


# ── Source health ────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_json(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        sources = data["sources"]
        # Must report IDX, BPS, KSEI
        assert "IDX" in sources
        assert "BPS" in sources
        assert "KSEI" in sources

    def test_health_source_has_status(self, client):
        resp = client.get("/api/health")
        sources = resp.json()["sources"]
        for name, info in sources.items():
            assert "status" in info

    def test_health_closes_ksei_client_on_fetch_failure(self, client, monkeypatch):
        import indonesia_data_mcp.ksei

        closed = False

        class FailingKSEIClient:
            async def sid_growth(self, **kwargs):
                raise RuntimeError("offline")

            async def close(self):
                nonlocal closed
                closed = True

        monkeypatch.setattr(indonesia_data_mcp.ksei, "KSEIClient", FailingKSEIClient)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["sources"]["KSEI"]["status"] == "error"
        assert closed is True

    def test_cross_origin_requests_are_not_permitted(self, client):
        resp = client.get("/api/health", headers={"Origin": "https://example.net"})
        assert "access-control-allow-origin" not in resp.headers


def test_app_closes_idx_client():
    from starlette.testclient import TestClient

    app = create_app()
    closed = False

    async def close():
        nonlocal closed
        closed = True

    app.state.idx.close = close
    with TestClient(app):
        pass
    assert closed is True


# ── Missions (demo data) ────────────────────────────────────────

class TestMissionsEndpoint:
    def test_list_missions(self, client):
        resp = client.get("/api/missions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Seed data should exist
        assert len(data) > 0

    def test_mission_shape(self, client):
        resp = client.get("/api/missions")
        mission = resp.json()[0]
        assert "id" in mission
        assert "title" in mission
        assert "state" in mission
        assert "demo" in mission  # Must flag as demo
        assert mission["demo"] is True

    def test_create_mission(self, client):
        resp = client.post(
            "/api/missions",
            json={"title": "Analyze BMRI", "ticker": "BMRI"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Analyze BMRI"
        assert data["state"] == "PENDING"
        assert data["demo"] is True

    @pytest.mark.parametrize(
        "payload",
        (
            [],
            {"title": 123, "ticker": "BMRI"},
            {"title": "Analyze", "ticker": "XX"},
            {"title": "x" * 121, "ticker": "BMRI"},
        ),
    )
    def test_create_mission_rejects_invalid_payload(self, client, payload):
        resp = client.post("/api/missions", json=payload)
        assert resp.status_code == 400

    def test_update_mission_state(self, client):
        # Get first mission id
        missions = client.get("/api/missions").json()
        mid = missions[0]["id"]
        resp = client.patch(
            f"/api/missions/{mid}/state",
            json={"state": "ACTIVE"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "ACTIVE"

    def test_update_mission_invalid_state(self, client):
        missions = client.get("/api/missions").json()
        mid = missions[0]["id"]
        resp = client.patch(
            f"/api/missions/{mid}/state",
            json={"state": "EXPLODED"},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("payload", ([], {"state": 123}))
    def test_update_mission_rejects_invalid_payload(self, client, payload):
        missions = client.get("/api/missions").json()
        resp = client.patch(
            f"/api/missions/{missions[0]['id']}/state",
            json=payload,
        )
        assert resp.status_code == 400

    def test_filter_missions_by_state(self, client):
        resp = client.get("/api/missions?state=PENDING")
        assert resp.status_code == 200
        data = resp.json()
        assert all(m["state"] == "PENDING" for m in data)


# ── Watchlist ────────────────────────────────────────────────────

class TestWatchlistEndpoint:
    def test_list_watchlist(self, client):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # BBCA must be in default watchlist
        tickers = [item["ticker"] for item in data]
        assert "BBCA" in tickers

    def test_watchlist_item_shape(self, client):
        resp = client.get("/api/watchlist")
        item = resp.json()[0]
        assert "ticker" in item
        assert "name" in item


# ── Company profile (live fallback) ─────────────────────────────

class TestCompanyEndpoint:
    def test_company_returns_data(self, client):
        resp = client.get("/api/company/BBCA")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "source" in data  # Must indicate official vs fallback

    def test_company_invalid_ticker(self, client):
        resp = client.get("/api/company/XX")
        assert resp.status_code == 400


# ── Announcements (live fallback) ───────────────────────────────

class TestAnnouncementsEndpoint:
    def test_announcements_returns_list(self, client):
        resp = client.get("/api/announcements/BBCA")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)


class TestFilingsEndpoint:
    def test_filings_returns_official_envelope(self, client):
        resp = client.get("/api/filings/BBCA?year=2025&period=audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "source" in data

    def test_filings_rejects_invalid_year(self, client):
        resp = client.get("/api/filings/BBCA?year=not-a-year")
        assert resp.status_code == 400


class TestEvidenceEndpoint:
    def test_evidence_returns_profile_announcements_and_filings(self, client):
        resp = client.get("/api/evidence/BBCA?year=2025&period=audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "BBCA"
        assert set(data["channels"]) == {"profile", "announcements", "filings"}
        assert data["official_only"] is all(
            channel["official"] for channel in data["channels"].values()
        )

    @pytest.mark.parametrize(
        "announcement_source_url",
        (
            "https://attacker.example/disclosure",
            "https://bad@www.idx.co.id/disclosure",
            "https://www.idx.co.id:444/disclosure",
        ),
    )
    def test_evidence_degrades_when_provenance_is_missing_or_unofficial(
        self, app, announcement_source_url
    ):
        from starlette.testclient import TestClient

        async def company_profile(ticker):
            return {"data": {"ticker": ticker}, "provenance": []}

        async def announcements(ticker, limit):
            return {
                "data": [],
                "provenance": [
                    {
                        "provider": "IDX",
                        "official": True,
                        "source_url": announcement_source_url,
                    }
                ],
            }

        async def financial_reports(**kwargs):
            return {
                "data": [],
                "provenance": [
                    {
                        "provider": "IDX",
                        "official": True,
                        "source_url": "https://www.idx.co.id/primary/ListedCompany/GetFinancialReport",
                    }
                ],
            }

        app.state.idx.company_profile = company_profile
        app.state.idx.announcements = announcements
        app.state.idx.financial_reports = financial_reports
        with TestClient(app) as client:
            data = client.get("/api/evidence/BBCA?year=2025&period=audit").json()

        assert data["official_only"] is False
        assert data["channels"]["profile"]["official"] is False
        assert data["channels"]["announcements"]["official"] is False
        assert data["channels"]["filings"]["official"] is True


# ── Agent operations (demo) ─────────────────────────────────────

class TestOperationsEndpoint:
    def test_operations_returns_list(self, client):
        resp = client.get("/api/operations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            op = data[0]
            assert "demo" in op
            assert op["demo"] is True


# ── Command log ─────────────────────────────────────────────────

class TestLogEndpoint:
    def test_log_returns_list(self, client):
        resp = client.get("/api/log")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ── Static file serving ─────────────────────────────────────────

class TestStaticServing:
    def test_root_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_css_served(self, client):
        resp = client.get("/static/styles.css")
        assert resp.status_code == 200
        assert "#0B132B" in resp.text
        assert "#00B8D4" in resp.text

    def test_js_served(self, client):
        resp = client.get("/static/app.js")
        assert resp.status_code == 200
        assert "/api/evidence/" in resp.text
        assert 'url.protocol === "https:" && url.hostname === "www.idx.co.id"' in resp.text
        assert "url.username || url.password" in resp.text
        assert 'url.port && url.port !== "443"' in resp.text
        assert 'href="${safeURL(' in resp.text

    def test_shell_has_operational_regions_and_demo_disclosure(self, client):
        html = client.get("/").text
        for text in (
            "IDX MISSION CONTROL",
            "SITUATION ROOM",
            "MISSION QUEUE",
            "AGENT OPERATIONS",
            "EVIDENCE VAULT",
            "COMMAND LOG",
            "DEMO WORKFLOW",
        ):
            assert text in html
