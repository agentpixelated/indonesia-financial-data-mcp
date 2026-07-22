# IDX Mission Control

## Product architecture

The dashboard is a lightweight Starlette application layered on the existing official-data clients. It does not duplicate IDX retrieval or parsing.

- `dashboard/app.py` — JSON API, demo mission state, graceful live-source envelopes
- `dashboard/static/index.html` — semantic command-room shell
- `dashboard/static/styles.css` — responsive KTI design system
- `dashboard/static/app.js` — client state and interactions
- `tests/test_dashboard.py` — API, validation, static-shell, and design-token contracts

### Data boundary

Official evidence channels are fetched from `IDXClient`:

- issuer profile, management, and disclosed shareholders
- announcements and original attachments
- financial-report records and original attachments

`GET /api/evidence/{ticker}` combines those independent channels and preserves each provenance envelope. It explicitly does not provide market prices, recommendations, or canonical cross-company normalization.

Mission queue and agent operations are in-memory demonstration state. Every such surface is visibly labelled `DEMO WORKFLOW` or `DEMO SIGNAL`.

## KTI design system

Authoritative tokens from the supplied KTI palette:

- Midnight Navy `#0B132B` — application shell and headers
- Electric Cyan `#00B8D4` — primary signal, focus, verified active state
- Bitcoin Orange `#F7931A` — demo/pending attention
- Future Violet `#6C63FF` — AI/agent workflow state
- Soft Background `#F5F7FB` — high-contrast source telemetry
- Pure White `#FFFFFF` — primary text on navy
- Primary Ink `#171A21` — text on light surfaces
- Secondary Navy `#16213E` — operational modules
- Muted Gray `#5B6472` — metadata
- Soft Border `#DDE5F0` — structure and separators
- Pale Blue Gray `#D8E1EF` — secondary text on navy

The interface uses square aerospace-instrument geometry, fine rules, compact telemetry, a subtle command grid, and only meaningful status motion. Reduced-motion preferences are respected.

## Run

```bash
.venv/bin/pip install -e '.[dashboard]'
.venv/bin/python -m dashboard --host 0.0.0.0 --port 8010
```

Open `http://localhost:8010`.

## Verified interactions

- issuer selection refreshes official evidence
- mission state filters
- announcement/filing channel switch
- evidence/provenance drawer
- create demo mission modal (`Ctrl/Cmd+M`)
- mobile command navigation
- source-health refresh every 60 seconds
- accessible keyboard focus and Escape-to-close

## Boundaries

- No licensed official market prices are displayed.
- No buy/sell recommendation is produced.
- Filing attachments are shown as official records, not normalized peer metrics.
- Mission and agent-operation data is not persisted and does not launch agents.
