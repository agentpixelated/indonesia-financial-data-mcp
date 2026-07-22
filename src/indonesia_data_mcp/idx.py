"""Official Indonesia Stock Exchange public-data client."""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Awaitable, Callable
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit

import httpx

from .filing import parse_instance_zip
from .http import OfficialHTTPClient
from .models import Provenance, envelope


class IDXClient:
    BASE = "https://www.idx.co.id"
    API = f"{BASE}/primary/ListedCompany"
    _TICKER_RE = re.compile(r"^[A-Z0-9]{4,8}$")
    _PERIODS = {"TW1", "TW2", "TW3", "AUDIT"}

    MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024

    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        browser_get_json: Callable[[str, dict[str, str]], Awaitable[Any]] | None = None,
        browser_get_bytes: Callable[[str, dict[str, str], int], Awaitable[bytes]] | None = None,
    ) -> None:
        self.transport = OfficialHTTPClient(http, min_interval=0.75)
        self._session_ready = False
        self._browser_transport_required = False
        self._browser_get_json = browser_get_json or self._curl_cffi_get_json
        self._browser_get_bytes = browser_get_bytes or self._curl_cffi_get_bytes

    @staticmethod
    async def _curl_cffi_get_json(url: str, headers: dict[str, str]) -> Any:
        """Use browser-compatible TLS only when IDX rejects ordinary HTTP TLS."""

        def fetch() -> Any:
            from curl_cffi import requests

            session = requests.Session(impersonate="chrome")
            session.get("https://www.idx.co.id/", headers=headers, timeout=30)
            response = session.get(url, headers=headers, timeout=45)
            response.raise_for_status()
            return response.json()

        return await asyncio.to_thread(fetch)

    @staticmethod
    async def _curl_cffi_get_bytes(
        url: str, headers: dict[str, str], max_bytes: int
    ) -> bytes:
        """Download an official attachment using browser-compatible TLS."""

        def fetch() -> bytes:
            from curl_cffi import requests

            session = requests.Session(impersonate="chrome")
            session.get("https://www.idx.co.id/", headers=headers, timeout=30)
            response = session.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            content = response.content
            if len(content) > max_bytes:
                raise RuntimeError("Official IDX attachment exceeds maximum size")
            return content

        return await asyncio.to_thread(fetch)

    async def close(self) -> None:
        await self.transport.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ticker(self, ticker: str) -> str:
        normalized = ticker.strip().upper()
        if not self._TICKER_RE.fullmatch(normalized):
            raise ValueError("ticker must be a 4-8 character IDX code without .JK")
        return normalized

    def _period(self, period: str) -> str:
        normalized = period.strip().upper()
        if normalized not in self._PERIODS:
            raise ValueError("period must be one of TW1, TW2, TW3, audit")
        return "audit" if normalized == "AUDIT" else normalized

    async def _ensure_session(self) -> None:
        if self._session_ready:
            return
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.BASE}/",
        }
        errors: list[str] = []
        # IDX's Cloudflare policy can vary by localized route. Start at the
        # canonical root, then try the English and Indonesian entry points.
        for path in ("/", "/en", "/id/"):
            try:
                await self.transport.request("GET", f"{self.BASE}{path}", headers=headers)
                self._session_ready = True
                return
            except RuntimeError as exc:
                errors.append(str(exc))
        self._browser_transport_required = True
        self._session_ready = True

    async def _get(self, path: str, params: dict[str, Any]) -> tuple[Any, str]:
        await self._ensure_session()
        query = urlencode(params)
        source_url = f"{self.API}/{path}?{query}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{self.BASE}/",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self._browser_transport_required:
            data = await self._browser_get_json(source_url, headers)
        else:
            try:
                data = await self.transport.get_json(source_url, headers=headers)
            except RuntimeError as exc:
                if "403 Forbidden" not in str(exc):
                    raise
                self._browser_transport_required = True
                data = await self._browser_get_json(source_url, headers)
        return data, source_url

    def _transport_warnings(self) -> list[str] | None:
        if self._browser_transport_required:
            return ["IDX required browser-compatible TLS transport"]
        return None

    def _source(self, source_url: str) -> Provenance:
        return Provenance(
            provider="IDX",
            source_url=source_url,
            retrieved_at=self._now(),
            official=True,
        )

    @staticmethod
    def _company(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "ticker": item.get("KodeEmiten"),
            "name": item.get("NamaEmiten"),
            "listing_date": item.get("TanggalPencatatan"),
            "sector": item.get("Sektor"),
            "subsector": item.get("SubSektor"),
            "industry": item.get("Industri"),
            "subindustry": item.get("SubIndustri"),
            "listing_board": item.get("PapanPencatatan"),
            "business_activity": item.get("KegiatanUsahaUtama"),
        }

    async def list_companies(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        raw, source_url = await self._get(
            "GetCompanyProfiles", {"start": offset, "length": limit}
        )
        rows = [self._company(item) for item in raw.get("data", [])]
        return envelope(
            rows,
            self._source(source_url),
            warnings=self._transport_warnings(),
            meta={"total": raw.get("recordsTotal", len(rows)), "offset": offset, "limit": limit},
        )

    async def company_profile(self, ticker: str, *, language: str = "id-id") -> dict[str, Any]:
        ticker = self._ticker(ticker)
        if language not in {"id-id", "en-us"}:
            raise ValueError("language must be id-id or en-us")
        raw, source_url = await self._get(
            "GetCompanyProfilesDetail", {"KodeEmiten": ticker, "language": language}
        )
        profiles = raw.get("Profiles") or []
        if not profiles:
            return envelope([], self._source(source_url), warnings=[f"No IDX profile for {ticker}"])
        profile = self._company(profiles[0])
        profile.update(
            {
                "address": profiles[0].get("Alamat"),
                "email": profiles[0].get("Email"),
                "phone": profiles[0].get("Telepon"),
                "website": profiles[0].get("Website"),
                "npwp": profiles[0].get("NPWP"),
                "directors": [
                    {"name": row.get("Nama"), "position": row.get("Jabatan")}
                    for row in raw.get("Direktur", [])
                ],
                "commissioners": [
                    {
                        "name": row.get("Nama"),
                        "position": row.get("Jabatan"),
                        "independent": row.get("Independen"),
                    }
                    for row in raw.get("Komisaris", [])
                ],
                "shareholders": [
                    {
                        "name": row.get("Nama"),
                        "shares": row.get("Jumlah"),
                        "percentage": row.get("Persentase"),
                        "category": row.get("Kategori"),
                        "controlling": row.get("Pengendali"),
                    }
                    for row in raw.get("PemegangSaham", [])
                ],
            }
        )
        return envelope(profile, self._source(source_url))

    async def announcements(
        self,
        ticker: str = "",
        *,
        limit: int = 50,
        offset: int = 0,
        date_from: str = "",
        date_to: str = "",
        language: str = "id",
    ) -> dict[str, Any]:
        ticker = self._ticker(ticker) if ticker else ""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        for value in (date_from, date_to):
            if value and not re.fullmatch(r"\d{8}", value):
                raise ValueError("dates must use YYYYMMDD")
        raw, source_url = await self._get(
            "GetAnnouncement",
            {
                "kodeEmiten": ticker,
                "indexFrom": offset,
                "pageSize": limit,
                "dateFrom": date_from,
                "dateTo": date_to,
                "lang": language,
            },
        )
        rows = []
        for item in raw.get("Replies", []):
            detail = item.get("pengumuman", {})
            rows.append(
                {
                    "id": detail.get("Id2"),
                    "number": detail.get("NoPengumuman"),
                    "date": detail.get("TglPengumuman"),
                    "ticker": (detail.get("Kode_Emiten") or "").strip(),
                    "title": detail.get("JudulPengumuman"),
                    "type": detail.get("JenisPengumuman"),
                    "subject": detail.get("PerihalPengumuman"),
                    "attachments": [
                        {
                            "filename": att.get("OriginalFilename") or att.get("PDFFilename"),
                            "download_url": urljoin(f"{self.BASE}/", att.get("FullSavePath") or ""),
                            "is_attachment": att.get("IsAttachment"),
                        }
                        for att in item.get("attachments", [])
                    ],
                }
            )
        return envelope(
            rows,
            self._source(source_url),
            meta={"total": raw.get("ResultCount", len(rows)), "offset": offset, "limit": limit},
        )

    async def financial_reports(
        self,
        ticker: str,
        year: int,
        period: str = "audit",
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        ticker = self._ticker(ticker)
        period = self._period(period)
        if not 2000 <= year <= 2100:
            raise ValueError("year must be between 2000 and 2100")
        raw, source_url = await self._get(
            "GetFinancialReport",
            {
                "periode": period,
                "year": year,
                "indexFrom": offset,
                "pageSize": limit,
                "reportType": "rdf",
                "kodeEmiten": ticker,
            },
        )
        reports = []
        for item in raw.get("Results", []):
            reports.append(
                {
                    "ticker": item.get("KodeEmiten"),
                    "name": item.get("NamaEmiten"),
                    "year": int(item.get("Report_Year")),
                    "period": item.get("Report_Period"),
                    "attachments": [
                        {
                            "id": att.get("File_ID"),
                            "filename": att.get("File_Name"),
                            "format": (att.get("File_Type") or "").lstrip(".").lower(),
                            "size_bytes": att.get("File_Size"),
                            "modified_at": att.get("File_Modified"),
                            "download_url": urljoin(f"{self.BASE}/", att.get("File_Path") or ""),
                        }
                        for att in item.get("Attachments", [])
                    ],
                }
            )
        warnings = [] if reports else [f"No {ticker} {year} {period} report found"]
        return envelope(
            reports,
            self._source(source_url),
            warnings=warnings,
            meta={"total": raw.get("ResultCount", len(reports))},
        )

    @staticmethod
    def _official_attachment_url(url: str) -> str:
        parts = urlsplit(url)
        if parts.scheme != "https" or (parts.hostname or "").lower() != "www.idx.co.id":
            raise ValueError("attachment must use an official IDX HTTPS URL")
        if parts.username or parts.password or parts.port not in (None, 443):
            raise ValueError("attachment must use an official IDX HTTPS URL")
        encoded_path = quote(parts.path, safe="/%:@-._~!$&'()*+,;=")
        return urlunsplit((parts.scheme, parts.netloc, encoded_path, parts.query, ""))

    async def filing_facts(
        self,
        ticker: str,
        year: int,
        period: str = "audit",
        *,
        concept: str = "",
        limit: int = 500,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return raw, queryable facts from an official IDX XBRL instance."""

        ticker = self._ticker(ticker)
        period = self._period(period)
        reports_result = await self.financial_reports(ticker, year, period)
        reports = reports_result.get("data", [])
        if not reports:
            raise ValueError(f"No {ticker} {year} {period} report found")

        report = reports[0]
        candidates = [
            attachment
            for attachment in report.get("attachments", [])
            if PurePosixPath(str(attachment.get("filename", ""))).name.lower()
            == "instance.zip"
        ]
        if len(candidates) != 1:
            raise ValueError("official filing must expose exactly one instance.zip attachment")
        attachment = candidates[0]
        download_url = self._official_attachment_url(str(attachment.get("download_url", "")))
        headers = {
            "Accept": "application/zip, application/octet-stream, */*",
            "Referer": f"{self.BASE}/",
        }
        content = await self._browser_get_bytes(
            download_url, headers, self.MAX_ATTACHMENT_BYTES
        )
        if len(content) > self.MAX_ATTACHMENT_BYTES:
            raise RuntimeError("Official IDX attachment exceeds maximum size")

        parsed = parse_instance_zip(
            content, concept=concept, limit=limit, offset=offset
        )
        digest = hashlib.sha256(content).hexdigest()
        attachment_result = {
            **attachment,
            "download_url": download_url,
            "downloaded_size_bytes": len(content),
            "sha256": digest,
        }
        data = {
            "filing": {
                "ticker": report.get("ticker"),
                "name": report.get("name"),
                "year": report.get("year"),
                "period": report.get("period"),
            },
            "attachment": attachment_result,
            "facts": parsed["facts"],
        }
        sources = [
            Provenance(
                provider=item.get("provider", "IDX"),
                source_url=item.get("source_url", ""),
                retrieved_at=item.get("retrieved_at", self._now()),
                official=bool(item.get("official", True)),
                source_format=item.get("source_format", "json"),
                notes=item.get("notes"),
            )
            for item in reports_result.get("provenance", [])
        ]
        sources.append(
            Provenance(
                provider="IDX",
                source_url=download_url,
                retrieved_at=self._now(),
                official=True,
                source_format="xbrl_zip",
                notes=f"SHA-256 {digest}",
            )
        )
        return envelope(
            data,
            *sources,
            warnings=[
                "Raw XBRL facts preserve issuer taxonomy and are not canonical normalization; concept names may differ across issuers and taxonomy versions"
            ],
            meta={
                "total": parsed["total"],
                "offset": parsed["offset"],
                "limit": parsed["limit"],
                "concept_filter": concept,
            },
        )
