"""Confirm the bug is NOT caused by `asyncio.to_thread` — reproduce it
with a direct synchronous call. If sync and to_thread both break
logging, the threading is irrelevant and the root cause is
`fileConfig(disable_existing_loggers=True)`.
"""

from __future__ import annotations

import asyncio
import logging
import logging.config
import sys
from pathlib import Path

ALEMBIC_INI = Path(__file__).resolve().parents[4] / "backend" / "alembic.ini"


def pretend_alembic_upgrade() -> None:
    """Mimic the fileConfig side-effect of alembic.command.upgrade."""
    logging.config.fileConfig(
        str(ALEMBIC_INI), defaults={"here": str(ALEMBIC_INI.parent)}
    )


def pretend_alembic_upgrade_in_thread() -> None:
    """Same side-effect; called via asyncio.to_thread."""
    logging.config.fileConfig(
        str(ALEMBIC_INI), defaults={"here": str(ALEMBIC_INI.parent)}
    )


def setup_uvicorn_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        stream=sys.stderr,
    )


async def run_sync_variant() -> None:
    print("\n--- VARIANT A: direct sync call (no to_thread) ---", file=sys.stderr)
    setup_uvicorn_logging()
    epubtv = logging.getLogger("epubtv")
    epubtv.info("BEFORE sync call")
    pretend_alembic_upgrade()  # same thread, no to_thread
    epubtv.info("AFTER sync call")
    _print_state(("epubtv",))


async def run_thread_variant() -> None:
    print("\n--- VARIANT B: asyncio.to_thread call ---", file=sys.stderr)
    setup_uvicorn_logging()
    epubtv = logging.getLogger("epubtv")
    epubtv.info("BEFORE to_thread call")
    await asyncio.to_thread(pretend_alembic_upgrade_in_thread)
    epubtv.info("AFTER to_thread call")
    _print_state(("epubtv",))


def _print_state(names: tuple[str, ...]) -> None:
    for name in names:
        lg = logging.getLogger(name)
        print(
            f"  {name}: disabled={lg.disabled} "
            f"effective={lg.isEnabledFor(logging.INFO)} "
            f"propagate={lg.propagate}",
            file=sys.stderr,
        )


async def main() -> None:
    await run_sync_variant()
    await run_thread_variant()


if __name__ == "__main__":
    asyncio.run(main())
