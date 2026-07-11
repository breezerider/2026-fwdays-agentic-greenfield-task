"""Fix 1: pass `disable_existing_loggers=False` to fileConfig in
`alembic/env.py`. This is the canonical Python-logging fix for the
"alembic clobbered my logger" class of bug.
"""

from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path

ALEMBIC_INI = Path(__file__).resolve().parents[4] / "backend" / "alembic.ini"


def setup_uvicorn_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        stream=sys.stderr,
    )


def alembic_fix_disable_existing() -> None:
    # The proposed one-line fix in alembic/env.py:
    #   fileConfig(config.config_file_name, disable_existing_loggers=False)
    logging.config.fileConfig(
        str(ALEMBIC_INI),
        defaults={"here": str(ALEMBIC_INI.parent)},
        disable_existing_loggers=False,
    )


def main() -> None:
    setup_uvicorn_logging()
    epubtv = logging.getLogger("epubtv")
    uvicorn_logger = logging.getLogger("uvicorn")
    print("== BEFORE alembic (with fix) ==", file=sys.stderr)
    epubtv.info("epubtv BEFORE alembic")
    uvicorn_logger.info("uvicorn BEFORE alembic")
    alembic_fix_disable_existing()
    print("== AFTER alembic (with fix) ==", file=sys.stderr)
    epubtv.info("epubtv AFTER alembic (FIX: should appear)")
    uvicorn_logger.info("uvicorn AFTER alembic (FIX: should appear)")


if __name__ == "__main__":
    main()
