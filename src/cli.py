#!/usr/bin/env python3
"""CLI entry point for agent-assistant package."""
import sys
from pathlib import Path

# Ensure the service module can be imported
from .service import main as service_main


def main():
    """Main CLI entry point."""
    # Print startup message
    print(f"🤖 Agent Assistant starting from: {Path.cwd()}")
    print(f"   Working directory will be indexed and used as workspace")
    print()

    # Run the service
    service_main()


if __name__ == "__main__":
    main()
