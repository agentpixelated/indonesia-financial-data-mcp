"""CLI entrypoint for IDX Mission Control dashboard.

Usage:
    python -m dashboard              # start on 0.0.0.0:8010
    python -m dashboard --port 9000  # custom port
    python -m dashboard --help
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dashboard",
        description="IDX Mission Control — operational dashboard for Indonesian financial data",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8010,
        help="Listen port (default: 8010)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    uvicorn.run(
        "dashboard.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
