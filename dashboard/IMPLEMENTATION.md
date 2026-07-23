# IDX Research Desk

## Product architecture

The dashboard is a lightweight Starlette application layered on the existing official-data clients. It does not duplicate IDX retrieval or parsing.

- `dashboard/app.py` — JSON API, local demonstration state, and live-source envelopes
- `dashboard/static/index.html` — semantic institutional research workspace
- `dashboard/static/styles.css` — responsive KTI design system and self-hosted Geist fonts
- `dashboard/static/app.js` — client state and accessible interactions
- `tests/test_dashboard.py` — API, validation, static-shell, provenance, and accessibility contracts

### Data boundary

Official evidence channels are fetched from `IDXClient`:

- issuer profile, management, and disclosed shareholders
- announcements and original attachments
- financial-report records and original attachments

`GET /api/evidence/{ticker}` combines those independent channels and preserves each provenance envelope. A channel is marked official only when its provenance contract identifies IDX and passes the HTTPS `www.idx.co.id` authority checks.

The issuer navigation is a local preset, not an official IDX dataset. Selecting an issuer loads the live IDX profile and disclosure channels. The research-task queue, processing queue, and audit log are in-memory demonstration state. These surfaces are explicitly marked `Demo` or `Simulated workflow`.

The dashboard does not provide market prices, recommendations, portfolio results, or canonical cross-company normalization.

## KTI design system

Authoritative tokens from the supplied KTI palette:

- Midnight Navy `#0B132B` — application shell and headers
- Electric Cyan `#00B8D4` — official evidence and active controls
- Bitcoin Orange `#F7931A` — simulated/demo states
- Future Violet `#6C63FF` — sparing secondary accent
- Soft Background `#F5F7FB` — workspace background
- Pure White `#FFFFFF` — primary surfaces
- Primary Ink `#171A21` — text on light surfaces
- Secondary Navy `#16213E` — supporting dark surfaces
- Muted Gray `#5B6472` — metadata
- Soft Border `#DDE5F0` — structure and separators
- Pale Blue Gray `#D8E1EF` — secondary structure

The interface uses flat institutional surfaces, fine separators, tabular metadata, and restrained state transitions. It has no gradients, glows, pulse effects, or fake telemetry. Geist Sans and Geist Mono are self-hosted under `dashboard/static/fonts/`, with the OFL license packaged alongside them. Reduced-motion preferences are respected.

## Run

```bash
.venv/bin/pip install -e '.[dashboard]'
.venv/bin/python -m dashboard --host 0.0.0.0 --port 8010
```

Open `http://localhost:8010`.

## Verified interactions

- issuer selection refreshes official evidence
- research-task state filters
- announcement/filing tabs, including Arrow Left/Right and Home/End keyboard control
- evidence/provenance drawer with focus trapping, Escape dismissal, and focus restoration
- create-demo-task modal with the same dialog focus behavior (`Ctrl/Cmd+M`)
- mobile workspace navigation with programmatic current-state exposure
- source-health refresh every 60 seconds
- responsive layouts at desktop, tablet, and mobile widths

## Boundaries

- Official attachment links must use HTTPS, exact host `www.idx.co.id`, no credentials, and only the default/443 port.
- No licensed official market prices are displayed.
- No buy/sell recommendation is produced.
- Filing attachments are shown as official records, not normalized peer metrics.
- Research tasks and processing operations are not persisted and do not launch agents.
