#!/usr/bin/env python3
"""Launcher script for the Hermes Meme Reaction Web Dashboard."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path to enable imports
root_path = Path(__file__).parent.resolve()
sys.path.insert(0, str(root_path))

try:
    from meme_reaction.web.server import start_server
except ImportError as e:
    print(f"Error: Failed to import the web dashboard backend. {e}")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the Hermes Meme Reaction Web Dashboard Control Center.")
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the dashboard on (default: 8000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind the dashboard to (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("        Hermes Meme Reaction Auto-Response Web Dashboard        ")
    print("=" * 60)
    print(f"Address: http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop the dashboard server.")
    print("-" * 60)

    try:
        start_server(port=args.port, host=args.host)
    except KeyboardInterrupt:
        print("\nDashboard server stopped.")
    except Exception as ex:
        print(f"\nFatal error starting dashboard: {ex}")
        sys.exit(1)


if __name__ in {"__main__", "__mp_main__"}:
    main()
