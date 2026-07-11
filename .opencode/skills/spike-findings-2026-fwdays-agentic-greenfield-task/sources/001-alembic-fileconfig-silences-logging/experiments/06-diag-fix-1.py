"""Diagnostic: does disable_existing_loggers=False actually re-enable
the epubtv logger, or is there a second issue (root level reset)?
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


def show_state(label: str) -> None:
    root = logging.getLogger()
    epubtv = logging.getLogger("epubtv")
    print(
        f"  [{label}] root.level={logging.getLevelName(root.level)} "
        f"root.handlers={[(type(h).__name__, logging.getLevelName(h.level)) for h in root.handlers]}",
        file=sys.stderr,
    )
    print(
        f"  [{label}] epubtv.disabled={epubtv.disabled} "
        f"epubtv.level={logging.getLevelName(epubtv.level)} "
        f"epubtv.propagate={epubtv.propagate} "
        f"epubtv.handlers={epubtv.handlers}",
        file=sys.stderr,
    )


def main() -> None:
    setup_uvicorn_logging()
    show_state("after-basicConfig")

    logging.config.fileConfig(
        str(ALEMBIC_INI),
        defaults={"here": str(ALEMBIC_INI.parent)},
        disable_existing_loggers=False,
    )
    show_state("after-fileConfig(disable=False)")

    epubtv = logging.getLogger("epubtv")
    print("\n== ATTEMPT TO LOG ==", file=sys.stderr)
    epubtv.info("epubtv INFO — should appear with fix")
    print(f"  isEnabledFor(INFO)={epubtv.isEnabledFor(logging.INFO)}", file=sys.stderr)

    # Direct handler write to see if the handler itself works.
    root = logging.getLogger()
    for h in root.handlers:
        print(
            f"  handler={type(h).__name__} level={logging.getLevelName(h.level)}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
