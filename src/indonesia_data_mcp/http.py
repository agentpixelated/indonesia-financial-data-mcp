"""Hardened async HTTP transport for official data sources."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any

import httpx


class OfficialHTTPClient:
    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        min_interval: float = 0.35,
    ) -> None:
        self._owned = http is None
        self.http = http or httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "id,en-US;q=0.9,en;q=0.8",
            },
        )
        self.retries = retries
        self.min_interval = min_interval
        self._last_request: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def close(self) -> None:
        if self._owned:
            await self.http.aclose()

    async def _pace(self, host: str) -> None:
        async with self._locks[host]:
            elapsed = time.monotonic() - self._last_request[host]
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_request[host] = time.monotonic()

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        host = httpx.URL(url).host or ""
        last_error: Exception | None = None
        for attempt in range(self.retries):
            await self._pace(host)
            try:
                response = await self.http.request(method, url, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < self.retries:
                        retry_after = response.headers.get("retry-after")
                        delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                        await asyncio.sleep(min(delay, 8))
                        continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Official source request failed: {url}: {last_error}")

    async def get_json(self, url: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        response = await self.request("GET", url, **kwargs)
        content_type = response.headers.get("content-type", "").lower()
        stripped = response.text.lstrip()
        if "json" not in content_type and not stripped.startswith(("{", "[")):
            raise RuntimeError(
                f"Expected JSON from official source, got {content_type or 'unknown content type'}: {url}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Invalid JSON from official source: {url}") from exc
