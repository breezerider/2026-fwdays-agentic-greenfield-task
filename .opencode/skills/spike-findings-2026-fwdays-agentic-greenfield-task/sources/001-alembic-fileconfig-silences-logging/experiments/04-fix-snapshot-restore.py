"""Fix 2 (defensive, app-side): snapshot the root logger + every
named logger before the alembic call, then restore state after.

Use this if you cannot modify `alembic/env.py` (e.g. third-party
alembic fork or a frozen dependency). In the epubtv project we own
`alembic/env.py` so fix 1 is preferred.
"""

from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path

ALEMBIC_INI = Path(__file__).resolve().parents[4] / "backend" / "alembic.ini"


def _snapshot() -> tuple[logging.Handler, list[logging.Logger], dict[str, dict]]:
    """Capture root handlers + every existing logger's state."""
    root = logging.getLogger()
    snapshot: dict[str, dict] = {}
    for name, lg in list(logging.root.manager.loggerDict.items()):
        if isinstance(lg, logging.PlaceHolder):
            continue
        snapshot[name] = {
            "disabled": lg.disabled,
            "propagate": lg.propagate,
            "level": lg.level,
            "filters": list(lg.filters),
        }
    # Handlers are shared objects, so we re-attach the same instances.
    return tuple(h for h in root.handlers), list(snapshot.keys()), snapshot


def _restore(saved_handlers: list, saved: dict) -> None:
    root = logging.getLogger()
    # Reset root: clear what fileConfig added, re-attach originals.
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in saved_handlers:
        root.addHandler(h)
    for name, state in saved.items():
        lg = logging.getLogger(name)
        lg.disabled = state["disabled"]
        lg.propagate = state["propagate"]
        lg.level = state["level"]
        lg.filters = state["filters"]


def setup_uvicorn_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        stream=sys.stderr,
    )


def main() -> None:
    setup_uvicorn_logging()
    epubtv = logging.getLogger("epubtv")
    print("== BEFORE alembic (with snapshot/restore) ==", file=sys.stderr)
    epubtv.info("epubtv BEFORE alembic")

    saved_handlers, _, saved_state = _snapshot()
    logging.config.fileConfig(
        str(ALEMBIC_INI), defaults={"here": str(ALEMBIC_INI.parent)}
    )
    _restore(saved_handlers, saved_state)

    print("== AFTER alembic (with snapshot/restore) ==", file=sys.stderr)
    epubtv.info("epubtv AFTER alembic (FIX: should appear)")


if __name__ == "__main__":
    main()
