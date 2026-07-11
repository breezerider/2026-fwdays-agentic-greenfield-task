"""Fix 4: snapshot full logging state (root handlers + root level +
every named logger's disabled flag) before the alembic call, restore
after. This is the most robust app-side fix — works regardless of
what alembic's fileConfig does to handlers, levels, or the disabled
flag.
"""

from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path

ALEMBIC_INI = Path(__file__).resolve().parents[4] / "backend" / "alembic.ini"


def _snapshot() -> dict:
    root = logging.getLogger()
    loggers: dict[str, dict] = {}
    for name, lg in list(logging.root.manager.loggerDict.items()):
        if isinstance(lg, logging.PlaceHolder):
            continue
        loggers[name] = {
            "disabled": lg.disabled,
            "propagate": lg.propagate,
            "level": lg.level,
            "filters": list(lg.filters),
        }
    return {
        "root_level": root.level,
        "root_handlers": list(root.handlers),
        "loggers": loggers,
    }


def _restore(snap: dict) -> None:
    root = logging.getLogger()
    # Reset root: clear what fileConfig added, re-attach originals.
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in snap["root_handlers"]:
        root.addHandler(h)
    root.setLevel(snap["root_level"])
    for name, state in snap["loggers"].items():
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
    uvicorn_logger = logging.getLogger("uvicorn")
    print("== BEFORE alembic (with full snapshot/restore) ==", file=sys.stderr)
    epubtv.info("epubtv BEFORE alembic")
    uvicorn_logger.info("uvicorn BEFORE alembic")

    snap = _snapshot()
    logging.config.fileConfig(
        str(ALEMBIC_INI), defaults={"here": str(ALEMBIC_INI.parent)}
    )
    _restore(snap)

    print("== AFTER alembic (with full snapshot/restore) ==", file=sys.stderr)
    epubtv.info("epubtv AFTER alembic (FIX: should appear)")
    uvicorn_logger.info("uvicorn AFTER alembic (FIX: should appear)")
    print(
        f"  epubtv: disabled={epubtv.disabled} "
        f"effective={epubtv.isEnabledFor(logging.INFO)} "
        f"propagate={epubtv.propagate}",
        file=sys.stderr,
    )
    print(
        f"  uvicorn: disabled={uvicorn_logger.disabled} "
        f"effective={uvicorn_logger.isEnabledFor(logging.INFO)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
