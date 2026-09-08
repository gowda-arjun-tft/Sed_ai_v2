"""Run the Layer 2 command adapter with concise operator errors."""

import sys

from .backend.cli import main


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
