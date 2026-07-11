# Lifespan Startup Logging (Alembic + Uvicorn)

## Requirements

- Migration contract from ADR 0013 is non-negotiable: alembic runs
  in-process inside the FastAPI lifespan (one `alembic upgrade head`
  per backend process), not via subprocess.
- The `asyncio.to_thread` wrapper is required to keep the event
  loop responsive while the synchronous migration runs.
- After the migration, the `epubtv` logger (and its descendants)
  must still emit records to whatever handler was wired by uvicorn
  / FastAPI / docker / pytest — without the operator having to
  reconfigure logging.
- Single-line change preferred. Patching `alembic/env.py` is in
  scope (it is a project file).

## How to Build It

### The fix (app-side, primary)

Wrap the `alembic_command.upgrade(cfg, "head")` call in
`backend/src/epubtv/tools/db_migrations.py:run_alembic_upgrade` with
a snapshot/restore of the relevant logging state. This is the
**only** change required for the logging bug.

```python
# backend/src/epubtv/tools/db_migrations.py

import logging

def _snapshot_logging() -> dict:
    """Snapshot root level + root handlers + every named logger's state."""
    root = logging.getLogger()
    loggers = {
        name: {
            "disabled": lg.disabled,
            "propagate": lg.propagate,
            "level": lg.level,
            "filters": list(lg.filters),
        }
        for name, lg in logging.root.manager.loggerDict.items()
        if isinstance(lg, logging.Logger)
    }
    return {
        "root_level": root.level,
        "root_handlers": list(root.handlers),
        "loggers": loggers,
    }


def _restore_logging(snap: dict) -> None:
    """Restore root level + root handlers + every named logger's state."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in snap["root_handlers"]:
        root.addHandler(h)
    root.setLevel(snap["root_level"])
    for name, st in snap["loggers"].items():
        lg = logging.getLogger(name)
        lg.disabled = st["disabled"]
        lg.propagate = st["propagate"]
        lg.level = st["level"]
        lg.filters = st["filters"]


# In run_alembic_upgrade(), wrap the alembic_command.upgrade call:
def run_alembic_upgrade() -> None:
    global _alembic_upgrade_done
    if _alembic_upgrade_done:
        return
    # ... existing parent-dir + cfg setup ...
    snap = _snapshot_logging()
    try:
        alembic_command.upgrade(cfg, "head")
    finally:
        _restore_logging(snap)
    _alembic_upgrade_done = True
```

### The fix (env.py, optional defense in depth)

In `backend/alembic/env.py:46`, change:

```python
fileConfig(config.config_file_name)
```

to:

```python
fileConfig(config.config_file_name, disable_existing_loggers=False)
```

This is the canonical alembic fix. It re-enables any pre-existing
loggers that the app might have created (uvicorn's, the app's,
third-party libraries'). It does NOT fix the root-level reset on
its own, but it makes the snapshot/restore defensive (catches the
case where someone adds a new logger in the future and forgets to
include it in the snapshot).

Apply **both** fixes together: snapshot/restore in
`db_migrations.py` + `disable_existing_loggers=False` in
`alembic/env.py`.

## What to Avoid

- **Do NOT** change `alembic.ini`'s `[logger_root] level` to NOTSET
  or INFO to "fix" the level reset. That changes alembic CLI
  behavior (`alembic current`, `alembic history`) for every dev
  and CI invocation. The fix belongs in the application seam.
- **Do NOT** switch back to subprocess alembic (pre-ADR-0013 path)
  to dodge the issue. ADR 0013 is locked and the subprocess path
  is retired; the in-process call is faster and the fix is
  smaller.
- **Do NOT** remove the `asyncio.to_thread` wrapper in the
  lifespan. It keeps the event loop responsive while alembic runs;
  the logging bug is independent of whether the call is in a
  thread. Removing the wrapper to "fix" the logging would mask the
  real bug.
- **Do NOT** rely on `disable_existing_loggers=False` alone. It
  re-enables the loggers but does NOT prevent the root level
  reset to WARNING by `[logger_root] level = WARNING`. INFO
  records from any non-disabled logger that propagates to root
  are still filtered.
- **Do NOT** skip the `alembic upgrade head` call — every
  entrypoint (uvicorn, docker, TestClient, Playwright) depends on
  it.

## Constraints

- Python's `logging.config.fileConfig` defaults to
  `disable_existing_loggers=True`. This is the root cause of the
  silencing — the `epubtv` + `uvicorn` loggers are not named in
  `alembic.ini`'s `[loggers]` section, so `fileConfig` walks the
  process-global `logging.root.manager.loggerDict` and sets
  `disabled=True` on every logger not in the config.
- `fileConfig` always applies `[logger_root]` regardless of
  `disable_existing_loggers`, so root level always drops to
  WARNING (from `alembic.ini`).
- These effects are **process-global**, not thread-local. Calling
  the same function via `asyncio.to_thread` (worker thread) or
  synchronously (event-loop thread) produces the same logging
  clobber. The fix must therefore be in-process-global too —
  snapshot/restore around the alembic call covers this.
- The fix must preserve the alembic-internal loggers
  (`alembic.runtime.migration`, `sqlalchemy.engine`) — these are
  not in the snapshot but are added by `fileConfig` to the logger
  dict, and removing them would break alembic's own log output.
  The snapshot iterates `loggerDict.items()` and captures all
  existing loggers; alembic's loggers are created inside the
  try block and live until the next `fileConfig` (which won't
  happen), so they survive the restore.

## Origin

Synthesized from spike: 001
Source files available in: `sources/001-alembic-fileconfig-silences-logging/`
Key files: `experiments/07-fix-full-snapshot.py` (the recommended
fix), `experiments/09-end-to-end-fix.py` (verification against the
real `epubtv.api.app` lifespan), `README.md` (full investigation
trail).
