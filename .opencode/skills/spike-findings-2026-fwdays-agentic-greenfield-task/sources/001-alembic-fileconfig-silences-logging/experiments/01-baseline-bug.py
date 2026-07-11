"""Reproduce the bug: uvicorn-style root logger + alembic fileConfig
(defaults) silences the `epubtv` logger.

Run from the repo root:
    python .planning/spikes/001-alembic-fileconfig-silences-logging/experiments/01-baseline-bug.py
"""

from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path

# Pretend to be uvicorn: wire a root handler that mirrors uvicorn's
# default config (StreamHandler to stderr, INFO level, plain format).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stderr,
)
epubtv = logging.getLogger("epubtv")
uvicorn_logger = logging.getLogger("uvicorn")

print("== BEFORE alembic ==", file=sys.stderr)
epubtv.info("epubtv BEFORE alembic (should appear)")
uvicorn_logger.info("uvicorn BEFORE alembic (should appear)")

# Mimic exactly what alembic/env.py:46 does on first alembic command.
# Defaults: disable_existing_loggers=True.
ALEMBIC_INI = Path(__file__).resolve().parents[4] / "backend" / "alembic.ini"
logging.config.fileConfig(str(ALEMBIC_INI), defaults={"here": str(ALEMBIC_INI.parent)})

print("== AFTER alembic (fileConfig default) ==", file=sys.stderr)
epubtv.info("epubtv AFTER alembic (BUG: should appear but doesn't)")
uvicorn_logger.info("uvicorn AFTER alembic (BUG: should appear but doesn't)")

# Forensics: show what fileConfig did to the existing loggers.
print("\n== LOGGER STATE ==", file=sys.stderr)
for name in ("root", "epubtv", "uvicorn", "alembic", "sqlalchemy"):
    lg = logging.getLogger(name)
    print(
        f"  {name}: disabled={lg.disabled} handlers={lg.handlers} "
        f"propagate={lg.propagate} effective={lg.isEnabledFor(logging.INFO)}",
        file=sys.stderr,
    )
root = logging.getLogger()
print(
    f"  root.handlers={[type(h).__name__ for h in root.handlers]}",
    file=sys.stderr,
)
