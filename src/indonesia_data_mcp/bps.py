"""Official Statistics Indonesia (BPS) WebAPI client."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from .http import OfficialHTTPClient
from .models import Provenance, envelope


class BPSClient:
    BASE = "https://webapi.bps.go.id/v1/api"

    def __init__(self, api_key: str, http: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key.strip()
        self.transport = OfficialHTTPClient(http, min_interval=0.35)

    async def close(self) -> None:
        await self.transport.close()

    def _require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "BPS_API_KEY is required. Create a key at https://webapi.bps.go.id/developer/"
            )

    async def _list(self, params: dict[str, Any]) -> tuple[dict[str, Any], str]:
        self._require_key()
        params = {**params, "key": self.api_key}
        request_url = f"{self.BASE}/list/?{urlencode(params)}"
        raw = await self.transport.get_json(request_url, headers={"Accept": "application/json"})
        if not isinstance(raw, dict):
            raise RuntimeError("Unexpected BPS response shape")
        if raw.get("status") != "OK":
            raise RuntimeError(f"BPS API error: {raw.get('message') or raw.get('status')}")
        return raw, request_url

    @staticmethod
    def _source(url: str) -> Provenance:
        return Provenance(
            provider="BPS",
            source_url=url,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            official=True,
        )

    @staticmethod
    def _page(raw: dict[str, Any]) -> tuple[dict[str, Any], list[Any]]:
        data = raw.get("data") or []
        if len(data) < 2 or not isinstance(data[0], dict) or not isinstance(data[1], list):
            return {}, []
        return data[0], data[1]

    async def list_subjects(
        self,
        *,
        domain: int = 0,
        language: str = "ind",
        page: int = 1,
        subject_category: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": "subject",
            "lang": language,
            "domain": f"{domain:04d}",
            "page": page,
        }
        if subject_category is not None:
            params["subcat"] = subject_category
        raw, url = await self._list(params)
        page_info, rows = self._page(raw)
        return envelope(rows, self._source(url), meta=page_info)

    async def list_variables(
        self,
        *,
        subject_id: int,
        domain: int = 0,
        language: str = "ind",
        page: int = 1,
    ) -> dict[str, Any]:
        raw, url = await self._list(
            {
                "model": "var",
                "lang": language,
                "domain": f"{domain:04d}",
                "subj": subject_id,
                "page": page,
            }
        )
        page_info, rows = self._page(raw)
        return envelope(rows, self._source(url), meta=page_info)

    async def get_data(
        self,
        *,
        variable_id: int,
        period_ids: str,
        domain: int = 0,
        language: str = "ind",
        derived_variable_id: int | None = None,
        vertical_variable_id: int | None = None,
        derived_period_ids: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": "data",
            "lang": language,
            "domain": f"{domain:04d}",
            "var": variable_id,
            "th": period_ids,
        }
        optional = {
            "turvar": derived_variable_id,
            "vervar": vertical_variable_id,
            "turth": derived_period_ids,
        }
        params.update({key: value for key, value in optional.items() if value is not None})
        raw, url = await self._list(params)
        data = {
            key: raw.get(key)
            for key in ("var", "turvar", "labelvervar", "vervar", "tahun", "turtahun", "datacontent")
            if key in raw
        }
        return envelope(data, self._source(url))
