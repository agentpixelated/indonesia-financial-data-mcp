"""Market-data tools backed by the fzn0x/idx CLI (MIT License).

Integration model — aggregation, not code copying:
    No source code from fzn0x/idx is copied into this repository. This
    module invokes the separately distributed ``idx`` binary (package
    ``ihsg-cli``) as a subprocess and wraps its JSON envelope in this
    project's provenance envelope. See THIRD_PARTY_NOTICES.md for the
    upstream copyright notice and license text.

Data labelling:
    Prices and fundamentals returned here come from Yahoo Finance / MSN
    Money via fzn0x/idx — they are NOT official IDX data, so every
    response carries ``official: False`` in its provenance, keeping the
    project's citation-first contract honest. The upstream MIT license
    covers the idx *software*; the market *data* remains subject to the
    terms of Yahoo Finance / MSN Money and is delayed, not licensed
    IDX real-time data.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

UPSTREAM_REPO = "https://github.com/fzn0x/idx"
UPSTREAM_NAME = "fzn0x/idx (ihsg-cli)"

Runner = Callable[[list[str]], Awaitable[tuple[int, str, str]]]


async def _subprocess_runner(argv: list[str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


class MarketUnavailable(RuntimeError):
    """Raised when the upstream idx binary is missing or fails."""


class MarketClient:
    def __init__(self, binary: str | None = None, runner: Runner | None = None) -> None:
        self.binary = binary or os.getenv("IDX_CLI_PATH", "idx")
        self._runner = runner or _subprocess_runner

    def available(self) -> bool:
        if os.path.sep in self.binary:
            return os.path.exists(self.binary)
        return shutil.which(self.binary) is not None

    async def _run(self, *args: str) -> dict[str, Any]:
        if not self.available():
            raise MarketUnavailable(
                "Upstream idx binary not found. Install it with "
                "`npm install -g ihsg-cli` (or set IDX_CLI_PATH). "
                f"See {UPSTREAM_REPO}"
            )
        code, out, err = await self._runner([self.binary, "-o", "json", *args])
        if code != 0:
            detail = err.strip()
            try:
                parsed = json.loads(detail.splitlines()[-1]) if detail else {}
                detail = parsed.get("error", {}).get("message", detail)
            except (ValueError, IndexError, AttributeError):
                pass
            raise MarketUnavailable(f"idx exited {code}: {detail}")
        try:
            envelope = json.loads(out)
        except ValueError as exc:
            raise MarketUnavailable(f"idx returned non-JSON output: {exc}") from exc
        return self._wrap(envelope, args)

    def _wrap(self, envelope: dict[str, Any], args: tuple[str, ...]) -> dict[str, Any]:
        provider = envelope.get("provider", "auto")
        return {
            "data": envelope.get("data", {}),
            "provenance": [
                {
                    "provider": f"{UPSTREAM_NAME} via {provider}",
                    "source_url": UPSTREAM_REPO,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "official": False,
                    "source_format": "json",
                    "note": (
                        "Delayed market data aggregated by Yahoo Finance / MSN Money "
                        "through the MIT-licensed fzn0x/idx CLI. Not official IDX data; "
                        "data use is subject to the upstream data providers' terms."
                    ),
                }
            ],
            "warnings": list(envelope.get("warnings", [])),
            "meta": {
                "upstream_schema": envelope.get("schema"),
                "upstream_fetched_at": envelope.get("fetched_at"),
                "cached": envelope.get("cached", False),
                "stale": envelope.get("stale", False),
                "command": "idx " + " ".join(args),
            },
        }

    async def quote(self, symbols: str) -> dict[str, Any]:
        return await self._run("stocks", "quote", symbols)

    async def history(
        self, symbol: str, period: str = "1y", interval: str = "1d", limit: int = 30
    ) -> dict[str, Any]:
        return await self._run(
            "stocks", "history", symbol,
            "--period", period, "--interval", interval, "--limit", str(limit),
        )

    async def fundamental(self, symbol: str) -> dict[str, Any]:
        return await self._run("stocks", "fundamental", symbol)

    async def technical(self, symbol: str, period: str = "1y") -> dict[str, Any]:
        return await self._run("stocks", "technical", symbol, "--period", period)

    async def screen(
        self, preset: str = "", filter_expr: str = "", sort: str = "", limit: int = 20
    ) -> dict[str, Any]:
        args = ["stocks", "screen"]
        if preset:
            args += ["--preset", preset]
        if filter_expr:
            args += ["-f", filter_expr]
        if sort:
            args += ["--sort", sort]
        args += ["-n", str(limit)]
        return await self._run(*args)

    async def foreign(self, symbol: str, days: int = 20) -> dict[str, Any]:
        return await self._run("stocks", "foreign", symbol, "--days", str(days))

    async def overview(self, top: int = 10) -> dict[str, Any]:
        return await self._run("market", "overview", "--top", str(top))

    async def indices(self) -> dict[str, Any]:
        return await self._run("market", "indices")

    async def ownership_ticker(self, symbol: str) -> dict[str, Any]:
        return await self._run("ownership", "ticker", symbol)
