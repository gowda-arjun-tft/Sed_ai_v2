"""What `python -m ML.deep_research.layer2` runs.

A thin wrapper whose only job is to turn an exception into one readable line
instead of a traceback, because the failures here are almost always operator
errors -- a wrong path, an empty fact sheet, a missing key -- and a stack trace
tells the reader nothing they need.
"""

import sys

from .cli import main


def _run() -> None:
    """Call `cli.main` and exit with its code, or print the error and exit 1.

    `SystemExit` deliberately passes through the `except`: it derives from
    `BaseException`, not `Exception`, so `main`'s own exit code -- including the
    1 that argparse raises on a bad argument -- is never swallowed and reprinted
    as an error.
    """
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    _run()
