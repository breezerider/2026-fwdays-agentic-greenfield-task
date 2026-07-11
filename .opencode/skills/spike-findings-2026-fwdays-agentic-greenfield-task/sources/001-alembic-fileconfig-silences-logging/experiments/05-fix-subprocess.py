"""Fix 3: run alembic through a real subprocess so its logging
changes never touch the parent process.

This is the pre-ADR-0013 path (subprocess.run([sys.executable, "-m",
"alembic", "upgrade", "head"])) and is preserved here as a known-good
fallback. ADR 0013 deprecated it in favour of in-process alembic for
faster cold starts; the logging price is fix 1 (one-line
`disable_existing_loggers=False` in `alembic/env.py`).

This script just runs the alembic CLI as a subprocess and lets the
parent logger prove it survives the round-trip.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"


def setup_uvicorn_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        stream=sys.stderr,
    )


def main() -> None:
    setup_uvicorn_logging()
    epubtv = logging.getLogger("epubtv")
    print("== BEFORE alembic subprocess ==", file=sys.stderr)
    epubtv.info("epubtv BEFORE alembic subprocess")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"== alembic exit={result.returncode} ==", file=sys.stderr)
    if result.stdout.strip():
        print(result.stdout, file=sys.stderr)
    if result.stderr.strip():
        print(result.stderr, file=sys.stderr)
    print("== AFTER alembic subprocess ==", file=sys.stderr)
    epubtv.info("epubtv AFTER alembic subprocess (FIX: should appear)")
    print(
        f"  epubtv.disabled={epubtv.disabled} "
        f"propagate={epubtv.propagate} effective={epubtv.isEnabledFor(logging.INFO)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
