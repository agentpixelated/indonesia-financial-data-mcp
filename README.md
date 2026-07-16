# Indonesia Financial Data MCP

Citation-first MCP server for **official Indonesian financial data**. It does not use Yahoo Finance or yfinance.

## v0.1 official sources

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
- `bps_list_subjects`
- `bps_list_variables`
- `bps_get_data`
- `ksei_sid_growth`
- `ksei_investor_demographics`
- `source_health`

See [`docs/SOURCES.md`](docs/SOURCES.md) for source contracts and boundaries,
and [`docs/HERMES.md`](docs/HERMES.md) for Hermes registration and live checks.

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

## Development

```bash
.venv/bin/pytest -q
```

Tests use fixtures/mock transports. Live smoke tests are separate so upstream availability cannot make the deterministic suite flaky.

## Scope and limitations

- IDX's public endpoints are protected by Cloudflare. The client establishes a
  normal IDX session and uses conservative pacing. If ordinary HTTP TLS is
  rejected, it retries with browser-compatible TLS via `curl_cffi`; it does not
  solve or bypass CAPTCHAs.
- This MCP returns official source records and attachments. Parsing financial-statement XLSX/XBRL/PDF into normalized line items is the next layer, not fabricated in v0.1.
- OJK's public data portal and Bank Indonesia sources were investigated. Their browser-facing services require additional contract discovery and reliability work, so they are not falsely advertised as production-ready tools in v0.1.
- Market-price data is not included: official IDX real-time/delayed market data is a licensed data product.

## License

MIT
