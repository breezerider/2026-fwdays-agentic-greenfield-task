---
spike: 001
name: alembic-fileconfig-silences-logging
type: standard
validates: "Given a uvicorn-style root handler is wired before the lifespan, when `alembic.command.upgrade` is invoked (sync or via `asyncio.to_thread`), then the `epubtv` + uvicorn loggers either keep emitting OR we identify the minimal one-line fix that restores them"
verdict: VALIDATED
related: []
tags: [logging, alembic, lifespan, asyncio, fastapi, uvicorn]
---

# Spike 001: alembic-fileconfig-silences-logging

## What This Validates

Given the FastAPI lifespan calls
`await asyncio.to_thread(run_alembic_upgrade)` (per ADR 0013 +
`backend/src/epubtv/api/app.py:132`), confirm:

1. **Why** does this silence log output from the FastAPI app's
   `epubtv` logger (and from uvicorn's own loggers)?
2. **Is it the threading** (`asyncio.to_thread`) or the alembic call
   itself that is the cause?
3. What is the **minimal fix** that preserves both the migration
   contract and the log capture?

## Research

### Smoking gun (in the project)

`backend/alembic/env.py:44-46`:

```python
# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
```

`backend/alembic.ini:117-129`:

```ini
[loggers]
keys = root,sqlalchemy,alembic

[logger_root]
level = WARNING
handlers = console
qualname =
```

### What `logging.config.fileConfig` does (Python docs)

`fileConfig(fname, defaults=None, disable_existing_loggers=True, ...)`.

- Reads `[loggers]`, `[handlers]`, `[formatters]` from the .ini.
- **If `disable_existing_loggers=True` (the default)**: walks
  `logging.root.manager.loggerDict` and sets `disabled=True` on
  every existing logger that is NOT named in the config.
- Always replaces root logger's `handlers` and `level` per
  `[logger_root]`.

### What this means in the epubtv project

- The `epubtv` logger is NOT in `alembic.ini`'s `[loggers]` keys.
  → after `fileConfig(alembic.ini)`, `epubtv.disabled = True`.
- The `uvicorn`, `uvicorn.error`, `uvicorn.access` loggers are also
  not in the `[loggers]` keys.
  → all three get `disabled = True` after the alembic call.
- `[logger_root] level = WARNING` resets root to WARNING.
  → INFO records from any non-disabled logger that propagates to
  root are also filtered.

All three effects are **process-global**, not thread-local. The
`asyncio.to_thread` wrapper is incidental — calling the same
function synchronously from the FastAPI event loop thread would
clobber logging identically.

### Existing fix attempts in the wild

The alembic docs (cookbook) recommend `disable_existing_loggers=False`
for this exact problem class. It re-enables existing loggers but
does NOT prevent the root-level reset (because `[logger_root]` is
always applied).

## How to Run

```bash
# Baseline: reproduce the bug
python3 .planning/spikes/001-alembic-fileconfig-silences-logging/experiments/01-baseline-bug.py

# Compare sync vs asyncio.to_thread (proves threading is not the cause)
python3 .planning/spikes/001-alembic-fileconfig-silences-logging/experiments/02-sync-vs-thread.py

# Fix 1: disable_existing_loggers=False (alone is insufficient — root level still drops)
python3 .planning/spikes/001-alembic-fileconfig-silences-logging/experiments/03-fix-disable-existing.py
python3 .planning/spikes/001-alembic-fileconfig-silences-logging/experiments/06-diag-fix-1.py

# Fix 2: full snapshot/restore in the lifespan (recommended — works for everything)
python3 .planning/spikes/001-alembic-fileconfig-silences-logging/experiments/07-fix-full-snapshot.py

# Fix 3: env.py change + minimal restore (format regresses to alembic's)
python3 .planning/spikes/001-alembic-fileconfig-silences-logging/experiments/08-fix-envpy-disable-false.py

# End-to-end: against the real epubtv FastAPI app
cd backend && uv run python3 ../.planning/spikes/001-alembic-fileconfig-silences-logging/experiments/09-end-to-end-fix.py
```

## What to Expect

- **Experiments 1-2**: `epubtv.disabled=True` after the alembic call.
  The "AFTER" log lines are silently swallowed.
- **Experiments 3, 6**: `disable_existing_loggers=False` re-enables
  the loggers, but `root.level` is still reset to WARNING. INFO
  records still get filtered at root.
- **Experiments 7, 8**: both the disabled flag AND the root level
  are restored. Both BEFORE and AFTER log lines appear.
- **Experiment 9**: the real `epubtv.api.app` lifespan runs the
  patched alembic helper; both `epubtv lifaspan called` and
  `epubtv initialized` show up in the captured log stream.

## Observability

Forensic log layer not required — each experiment script prints
per-logger state (disabled flag, level, effective, handlers) at
each transition so the cause-and-effect is auditable in the
output.

## Investigation Trail

### T1 — Confirm hypothesis: fileConfig clobbers `epubtv`

Ran experiment 1. Output:

```
epubtv: disabled=True handlers=[] propagate=True effective=False
uvicorn: disabled=True handlers=[] propagate=True effective=False
root.handlers=['StreamHandler']
```

Both `epubtv` and `uvicorn` are `disabled=True` and `effective=False`
for INFO. Root has a single StreamHandler, but the disabled
loggers emit nothing. **Hypothesis confirmed.**

### T2 — Isolate thread from cause

Ran experiment 2. Output:

```
--- VARIANT A: direct sync call (no to_thread) ---
  epubtv: disabled=True effective=False propagate=True
--- VARIANT B: asyncio.to_thread call ---
  epubtv: disabled=True effective=False propagate=True
```

Both variants show `epubtv.disabled=True`. The threading wrapper
makes no difference. The root cause is the `fileConfig` call inside
`alembic/env.py`, full stop. **`asyncio.to_thread` is innocent.**

### T3 — Try the canonical alembic fix

Experiment 3 passes `disable_existing_loggers=False`. The "AFTER"
line still doesn't appear. Output is silent between
"== AFTER alembic (with fix) ==" and the next `==` header.

### T4 — Diagnose why fix 1 is insufficient

Experiment 6 prints per-logger state after the fix. Output:

```
[after-fileConfig(disable=False)] root.level=WARNING
[after-fileConfig(disable=False)] epubtv.disabled=False epubtv.level=NOTSET
isEnabledFor(INFO)=False
```

`disable_existing_loggers=False` re-enables `epubtv`, but root's
level is reset to WARNING by `alembic.ini`'s `[logger_root]
level = WARNING`. INFO records from `epubtv` propagate to root and
get filtered there. **Two issues, not one.**

### T5 — Full snapshot/restore

Experiment 7 captures root level + root handlers + every named
logger's `disabled/propagate/level/filters` before the alembic
call, restores them after. Both BEFORE and AFTER log lines appear,
with the original uvicorn format and level preserved. **Works.**

### T6 — Minimal env.py change + minimal restore

Experiment 8 combines `disable_existing_loggers=False` (the env.py
one-liner) with restoring root level + the two loggers' disabled
flags after the call. Both lines appear, but the format regresses
to alembic's `%(levelname)-5.5s [%(name)s] %(message)s` because
root.handlers are now alembic's `console` handler, not uvicorn's
original. **Logs work; format regresses.**

### T7 — End-to-end against the real app

Experiment 9 imports the real `epubtv.api.app`, drives the lifespan
in-process via `app.router.lifespan_context`, and captures log
output via a custom handler. With the snapshot/restore fix
wrapped around `run_alembic_upgrade`, both `epubtv lifaspan called`
(BEFORE) and `epubtv initialized` (AFTER) appear. **Verified
against the real codebase.**

### T8 — Side observation (out of scope for this spike)

`backend/src/epubtv/tools/db_migrations.py:109` declares
`async def run_alembic_upgrade()`. It awaits
`alembic_command.upgrade(cfg, "head")` which is a sync function
and returns a coroutine that is never awaited (the test script's
`RuntimeWarning: coroutine 'run_alembic_upgrade' was never
awaited` surfaces this). Calling it via `asyncio.to_thread` works
because `to_thread` awaits whatever the thread returns, but the
internal `await alembic_command.upgrade(...)` line is a latent
bug. **Not the cause of the logging issue** — the lifespan still
runs and the logging clobber still happens — but worth flagging
for a follow-up spike.

## Results

### Verdict: VALIDATED

Three things confirmed:

1. **Root cause is `logging.config.fileConfig` in
   `alembic/env.py:46`, not the `asyncio.to_thread` wrapper.**
   `fileConfig` with default `disable_existing_loggers=True` sets
   `disabled=True` on every existing logger not named in
   `alembic.ini`'s `[loggers]` section. The `epubtv` and `uvicorn`
   loggers are not in that section, so they are silenced. Root
   level is also reset to WARNING by `[logger_root]`.

2. **The threading is irrelevant.** Both direct sync calls and
   `asyncio.to_thread` calls trigger the same `fileConfig`
   side-effects on the global root logger + global logger dict.
   These are process-global, not thread-local.

3. **Two minimal fixes are available; the recommended one is
   app-side snapshot/restore.**

### Recommended fix (primary)

Wrap the `alembic` call in `backend/src/epubtv/tools/db_migrations.py`
with a snapshot/restore of the relevant logging state:

```python
# In run_alembic_upgrade, around the alembic_command.upgrade call:
def _snapshot_logging() -> dict:
    root = logging.getLogger()
    loggers = {
        name: {"disabled": lg.disabled, "propagate": lg.propagate,
               "level": lg.level, "filters": list(lg.filters)}
        for name, lg in logging.root.manager.loggerDict.items()
        if isinstance(lg, logging.Logger)
    }
    return {"root_level": root.level, "root_handlers": list(root.handlers),
            "loggers": loggers}

def _restore_logging(snap: dict) -> None:
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

# In run_alembic_upgrade:
snap = _snapshot_logging()
try:
    alembic_command.upgrade(cfg, "head")
finally:
    _restore_logging(snap)
```

Why this and not the env.py one-liner:

- The env.py one-liner (`disable_existing_loggers=False`) is the
  canonical alembic fix but **does not solve the root-level
  reset**. INFO records from any logger that propagates to root
  are still filtered by `[logger_root] level = WARNING`.
- The snapshot/restore approach is **complete**: it preserves
  every aspect of the previous logging config (handlers, level,
  disabled flags) regardless of what `fileConfig` does.
- The cost is ~15 lines in one file (`db_migrations.py`) — no
  alembic.ini or env.py changes required, no alembic CLI behavior
  change.

### Optional secondary fix (defense in depth)

In `backend/alembic/env.py:46`, change:
```python
fileConfig(config.config_file_name)
```
to:
```python
fileConfig(config.config_file_name, disable_existing_loggers=False)
```

This is the alembic-community-recommended pattern. It re-enables
any pre-existing loggers that the app might have created
(uvicorn's, the app's, third-party libraries'). It does NOT fix
the root-level reset on its own, but it makes the snapshot/restore
defensive (catches the case where someone adds a new logger in
the future and forgets to include it in the snapshot).

If both are applied, the snapshot/restore handles root level +
root handlers, and the env.py change handles any logger that
wasn't in the snapshot. **Both are in scope of the same fix.**

### Anti-patterns to avoid

- **Do NOT remove the `asyncio.to_thread` wrapper** in the
  lifespan. It keeps the event loop responsive while alembic runs;
  the logging bug is independent of whether the call is in a
  thread.
- **Do NOT change `alembic.ini`'s `[logger_root] level` to NOTSET
  or INFO** to "fix" the level reset. That changes alembic CLI
  behavior (`alembic current`, `alembic history`) for every dev
  and CI invocation. The fix belongs in the application seam.
- **Do NOT switch back to subprocess alembic** (pre-ADR-0013
  path) to dodge the issue. ADR 0013 is locked and the subprocess
  path is retired; the in-process call is faster and the fix is
  smaller.
- **Do NOT skip the `alembic upgrade head` call** — every entrypoint
  (uvicorn, docker, TestClient, Playwright) depends on it.

### Out-of-scope follow-ups (flagged, not fixed)

- `db_migrations.py:109` declares `async def run_alembic_upgrade`
  but awaits a sync `alembic_command.upgrade` which produces a
  `RuntimeWarning: coroutine 'run_alembic_upgrade' was never
  awaited` in tests. Latent bug, not the cause of the logging
  issue, but should be a follow-up spike.

## Impact

- The fix is local to `backend/src/epubtv/tools/db_migrations.py`
  (one new helper + one ~5-line wrap around the existing
  `alembic_command.upgrade` call).
- ADR 0013 (in-process alembic) is preserved.
- `--workers 1` (mandatory) and all other locked-stack constraints
  are unaffected.
- The fix restores `epubtv` + `uvicorn` log capture in:
  - `uv run uvicorn` local dev
  - `docker compose up` (the demo container)
  - Playwright `webServer` (E2E tests)
  - TestClient / `ASGITransport` (BDD tests)
