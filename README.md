# Indonesia Financial Data MCP

Citation-first MCP server for **official Indonesian financial data**. The official
tools below do not use Yahoo Finance or yfinance. Optional market-data tools
(labelled `market_*` / `ownership_holders`) are provided separately through the
MIT-licensed [fzn0x/idx](https://github.com/fzn0x/idx) CLI and are always
labelled `official: false` — see "Market data (optional, non-official)".

## Official sources

| Provider | Coverage | Access |
|---|---|---|
| IDX | Issuer directory, detailed company profile, management/shareholders, announcements, financial-report attachments (XLSX/PDF/XBRL) | Public web endpoints; session cookie initialized automatically |
| BPS | Subjects, variables, dynamic statistical tables | Official WebAPI; requires free `BPS_API_KEY` |
| KSEI | SID growth and investor demographics | Public JSON endpoints |

Every successful response has:

```json
{
  "data": {},
  "provenance": [
    {
      "provider": "IDX",
      "source_url": "https://www.idx.co.id/...",
      "retrieved_at": "2026-07-16T00:00:00+00:00",
      "official": true,
      "source_format": "json"
    }
  ],
  "warnings": [],
  "meta": {}
}
```

Credential values are redacted from provenance URLs.

## Tools

- `idx_list_companies`
- `idx_company_profile`
- `idx_company_announcements`
- `idx_financial_reports`
- `idx_filing_facts`
- `bps_list_subjects`
- `bps_list_variables`
- `bps_get_data`
- `ksei_sid_growth`
- `ksei_investor_demographics`
- `source_health`

See [`docs/SOURCES.md`](docs/SOURCES.md) for source contracts and boundaries,
and [`docs/HERMES.md`](docs/HERMES.md) for Hermes registration and live checks.

## Market data (optional, non-official) — via fzn0x/idx

Official IDX market prices are a licensed product, so the official tools above
carry none. For delayed prices and screening, this server can delegate to the
**fzn0x/idx** CLI (`ihsg-cli`, MIT License, Copyright (c) 2026 Midori Research
and idx contributors — full text in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)):

```bash
npm install -g ihsg-cli        # or: cargo install --locked ihsg-cli
# optional: export IDX_CLI_PATH=/path/to/idx
```

No upstream code is copied into this repository; the server invokes the `idx`
binary as a subprocess (`idx -o json ...`) and wraps its output in the same
provenance envelope, with `official: false` and a note that the data is delayed
Yahoo Finance / MSN Money aggregation subject to those providers' terms.

Additional tools when the binary is present:

- `market_quote` — delayed quotes for one or more tickers
- `market_history` — OHLCV candles
- `market_fundamental` — ratios + upstream rule-based verdict (not a recommendation)
- `market_technical` — RSI/MACD/MA/Bollinger/ATR
- `market_screen` — screen ~950 IDX tickers by preset or filter expression
- `market_foreign` — foreign buy/sell per session (idx.co.id summaries)
- `market_overview`, `market_indices` — IHSG and all IDX indices
- `ownership_holders` — KSEI >1% holders (needs a prior `idx ownership sync` on the host)

`source_health` reports the backend as `fzn_idx_market`.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Optional BPS setup:

1. Create a key at <https://webapi.bps.go.id/developer/>.
2. Export it as `BPS_API_KEY` or configure it in the MCP client's scoped environment.

Run over stdio:

```bash
.venv/bin/python -m indonesia_data_mcp.server
```

Hermes registration (run from the repository root):

```bash
hermes mcp add indonesia-official \
  --command "$PWD/.venv/bin/python" \
  --args -m indonesia_data_mcp.server
```

If BPS is enabled, add `BPS_API_KEY` to Hermes's secret environment rather than Markdown or command history.

## IDX Research Desk dashboard

Run the responsive evidence-first dashboard on the LAN:

```bash
.venv/bin/pip install -e '.[dashboard]'
.venv/bin/python -m dashboard --host 0.0.0.0 --port 8010
```

Open `http://localhost:8010`. Official issuer, announcement, and filing data is
kept separate from clearly labelled in-memory demo workflow state. The dashboard
does not display unlicensed market prices or investment recommendations.

## Development

```bash
.venv/bin/pytest -q
```

Live tests are separate so upstream availability cannot make the deterministic suite flaky.

### Query official XBRL facts

`idx_filing_facts` resolves the requested IDX filing, downloads its official
`instance.zip`, verifies the ZIP, calculates SHA-256, and exposes its raw XBRL
facts with context periods, dimensions, units, decimals, and citations. Use the
optional `concept` substring to keep responses small—for example, `Assets`,
`ProfitLoss`, or `InterestIncome`.

The tool deliberately preserves the filing's taxonomy and raw values. It does
not claim canonical cross-company normalization: concept names can vary by
issuer profile and taxonomy version.

## Scope and limitations

- IDX's public endpoints are protected by Cloudflare. The client establishes a
  normal IDX session and uses conservative pacing. If ordinary HTTP TLS is
  rejected, it retries with browser-compatible TLS via `curl_cffi`; it does not
  solve or bypass CAPTCHAs.
- This MCP returns official source records and attachments. It can query raw
  `instance.zip` XBRL facts, but canonical cross-company line-item
  normalization remains a separate future layer.
- OJK's public data portal and Bank Indonesia sources were investigated. Their browser-facing services require additional contract discovery and reliability work, so they are not falsely advertised as production-ready tools in v0.1.
- Official market-price data is not included: official IDX real-time/delayed market data is a licensed data product. Delayed, non-official prices are available only through the optional fzn0x/idx backend described above, and are labelled `official: false`.

## License

MIT