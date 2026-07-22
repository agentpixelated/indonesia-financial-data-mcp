# Hermes setup

Install and test locally:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
```

Register the stdio server:

```bash
hermes mcp add indonesia-official \
  --command "$PWD/.venv/bin/python" \
  --args -m indonesia_data_mcp.server
```

Select all discovered tools, then verify:

```bash
hermes mcp test indonesia-official
```

Hermes should discover 11 tools. Start a new Hermes session after registering
so the tool schemas are loaded into the session.

For BPS, provide `BPS_API_KEY` through Hermes's scoped MCP environment or your
secret-management layer. Do not commit it or put it in documentation.

## Live smoke tests

```bash
RUN_LIVE=1 .venv/bin/pytest tests/test_live_smoke.py -q -vv
```

Live tests are opt-in because upstream availability and Cloudflare policy must
not make the deterministic fixture suite flaky.
