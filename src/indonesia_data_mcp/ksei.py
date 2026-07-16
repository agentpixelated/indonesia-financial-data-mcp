"""Official KSEI public statistics client."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from .http import OfficialHTTPClient
from .models import Provenance, envelope


class KSEIClient:
    BASE = "https://www.ksei.co.id"
    API = f"{BASE}/api/investor_demographic"

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self.transport = OfficialHTTPClient(http, min_interval=0.35)

    async def close(self) -> None:
        await self.transport.close()

    @staticmethod
    def _source(url: str) -> Provenance:
        return Provenance(
            provider="KSEI",
            source_url=url,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            official=True,
        )

    async def _get(self, path: str, params: dict[str, Any]) -> tuple[dict[str, Any], str]:
        url = f"{self.API}/{path}?{urlencode(params)}"
        raw = await self.transport.get_json(
            url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Referer": f"{self.BASE}/id/publikasi/data-dan-statistik/statistik-ksei",
            },
        )
        if not isinstance(raw, dict):
            raise RuntimeError("Unexpected KSEI response shape")
        return raw, url

    async def sid_growth(self, *, month_year: str, metric: str) -> dict[str, Any]:
        raw, url = await self._get(
            "sid_growths",
            {
                "locale": "id",
                "filter[three_years_data]": month_year,
                "filter[type]": metric,
            },
        )
        rows = [
            {
                "period": row.get("month"),
                "metric": row.get("type"),
                "value": row.get("asset_local"),
            }
            for row in raw.get("data", [])
        ]
        return envelope(rows, self._source(url))

    async def investor_demographics(
        self, *, month_year: str, dimension: str
    ) -> dict[str, Any]:
        allowed = {
            "gender": "gender",
            "age": "age",
            "education": "education",
            "job": "job_demographics",
            "income": "income",
        }
        if dimension not in allowed:
            raise ValueError(f"dimension must be one of {', '.join(allowed)}")
        params: dict[str, Any] = {
            "locale": "id",
            "filter[published]": "true",
            "filter[month_year]": month_year,
        }
        if dimension != "gender":
            params["sort"] = "order"
        raw, url = await self._get(f"individual/{allowed[dimension]}", params)
        return envelope(raw.get("data", []), self._source(url), meta={"dimension": dimension})
