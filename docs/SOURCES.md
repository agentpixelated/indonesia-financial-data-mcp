# Source contracts

The MCP exposes only sources verified against their official domains. Every
response carries an `official` flag, retrieval timestamp, and source URL.

## IDX

Base domain: <https://www.idx.co.id>

| Capability | Official endpoint |
|---|---|
| Issuer directory | `/primary/ListedCompany/GetCompanyProfiles` |
| Issuer details | `/primary/ListedCompany/GetCompanyProfilesDetail` |
| Announcements | `/primary/ListedCompany/GetAnnouncement` |
| Financial reports | `/primary/ListedCompany/GetFinancialReport` |

Financial-report records expose the original IDX XLSX, PDF, XBRL ZIP, and
inline-XBRL ZIP attachments. The MCP does not manufacture statement values.
Cloudflare can reject ordinary HTTP TLS fingerprints; in that case, the client
uses `curl_cffi` with browser-compatible TLS and reports a warning.

`idx_filing_facts` accepts only HTTPS attachments on `www.idx.co.id`, selects
the filing's `instance.zip`, enforces compressed and uncompressed size limits,
rejects unsafe ZIP paths and XML DTD/entities, and records the attachment's
SHA-256. Returned facts retain their original QName, context, dimensions, unit,
decimals, and raw value. They are queryable source facts—not canonical
normalization across issuers or taxonomy versions.

## BPS

Documentation: <https://webapi.bps.go.id/documentation/>

BPS's official WebAPI requires a free key. The MCP reads it from
`BPS_API_KEY`, passes it to BPS, and redacts it from returned provenance URLs.
Covered models are `subject`, `var`, and `data`.

## KSEI

Base domain: <https://www.ksei.co.id>

The MCP reads KSEI's public investor-demographic JSON endpoints for SID growth
and individual demographic dimensions. These data describe market-level
investor statistics, not issuer beneficial-owner registers.

## Deliberately excluded from v0.1

- Official IDX real-time/delayed prices: licensed IDX data products.
- OJK portal: official but its public browser API needs a stable documented
  contract before inclusion.
- Bank Indonesia: official pages rejected this host during verification; no
  brittle scraper is advertised as a production tool.
- PDF OCR/table extraction: separate roadmap item.
