"""CLI entrypoint for the IDX Research Desk dashboard.

Usage:
    python -m dashboard              # start on 0.0.0.0:8010
    python -m dashboard --port 9000  # custom port
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dashboard",
        description="IDX Research Desk — evidence-first dashboard for Indonesian financial data",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="bind host (default: 0.0.0.0 for LAN access)",
    )
    parser.add_argument("--port", type=int, default=8010, help="bind port (default: 8010)")
    parser.add_argument("--reload", action="store_true", help="enable development reload")
    args = parser.parse_args()

    uvicorn.run(
        "dashboard.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


__all__ = ["main"]
