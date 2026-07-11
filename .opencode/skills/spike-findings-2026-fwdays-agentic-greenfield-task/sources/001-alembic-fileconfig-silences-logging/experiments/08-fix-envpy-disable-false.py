"""Fix 5 (recommended): the canonical alembic fix is a one-line
change in `backend/alembic/env.py`:

    fileConfig(config.config_file_name, disable_existing_loggers=False)

Then the lifespan (or the db_migrations helper) still needs to deal
with the root level being reset to WARNING by
``[logger_root] level = WARNING`` in alembic.ini. The cleanest
companion fix is to NOT downgrade root in alembic.ini — but that
changes alembic CLI behavior. A safer alternative is to re-apply
the root level after the alembic call.

This script demonstrates BOTH halves together:
  1. ``disable_existing_loggers=False`` is the env.py change.
  2. Root level reset is handled in the lifespan by remembering
     the pre-alembic root level and restoring it.
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


def alembic_call_with_disable_false() -> None:
    # Stand-in for what alembic/env.py will look like after the fix.
    logging.config.fileConfig(
        str(ALEMBIC_INI),
        defaults={"here": str(ALEMBIC_INI.parent)},
        disable_existing_loggers=False,
    )


def main() -> None:
    setup_uvicorn_logging()
    epubtv = logging.getLogger("epubtv")
    uvicorn_logger = logging.getLogger("uvicorn")
    print("== BEFORE alembic ==", file=sys.stderr)
    epubtv.info("epubtv BEFORE alembic")
    uvicorn_logger.info("uvicorn BEFORE alembic")

    # Save state we care about (root level + a couple of loggers).
    saved_root_level = logging.getLogger().level
    saved_epubtv_disabled = epubtv.disabled
    saved_uvicorn_disabled = uvicorn_logger.disabled

    # Run alembic (with the env.py fix applied).
    alembic_call_with_disable_false()

    # Restore the bits fileConfig clobbered.
    logging.getLogger().setLevel(saved_root_level)
    epubtv.disabled = saved_epubtv_disabled
    uvicorn_logger.disabled = saved_uvicorn_disabled

    print("== AFTER alembic ==", file=sys.stderr)
    epubtv.info("epubtv AFTER alembic (FIX: should appear)")
    uvicorn_logger.info("uvicorn AFTER alembic (FIX: should appear)")
    print(
        f"  root.level={logging.getLevelName(logging.getLogger().level)} "
        f"epubtv.disabled={epubtv.disabled} "
        f"uvicorn.disabled={uvicorn_logger.disabled}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
