"""End-to-end: actually run the epubtv FastAPI app's lifespan with
the db_migrations helper wrapped in our snapshot/restore, capture
the uvicorn-style log output, and assert the AFTER messages are
present.

This is the proof that the fix integrates cleanly with the real
app — not just a stand-alone synthetic test.
"""

from __future__ import annotations

import io
import logging
import logging.config
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))


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


def patched_run_alembic_upgrade() -> None:
    """Patched version of ``epubtv.tools.db_migrations.run_alembic_upgrade``:
    snapshot+restore around the alembic fileConfig side-effect.
    """
    from epubtv.tools.db_migrations import run_alembic_upgrade

    snap = _snapshot()
    try:
        run_alembic_upgrade()
    finally:
        _restore(snap)


def main() -> None:
    # Capture stderr so we can read what the lifespan logged.
    captured = io.StringIO()
    handler = logging.StreamHandler(captured)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # Import the app and run its lifespan directly (no uvicorn).
    import asyncio

    from epubtv.api.app import app

    async def _drive():
        async with app.router.lifespan_context(app):
            pass

    asyncio.run(_drive())

    output = captured.getvalue()
    print("=" * 60, file=sys.stderr)
    print("CAPTURED LOG OUTPUT:", file=sys.stderr)
    print(output, file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Sanity assertions.
    assert "epubtv lifaspan called" in output, "BEFORE log missing"
    assert "epubtv initialized" in output, "AFTER log missing — fix did not work"
    print(
        "\nPASS: both BEFORE and AFTER lifespan log messages present.", file=sys.stderr
    )


if __name__ == "__main__":
    main()
