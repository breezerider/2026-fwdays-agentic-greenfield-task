---
name: spike-findings-2026-fwdays-agentic-greenfield-task
description: Implementation blueprint from spike experiments. Requirements, proven patterns, and verified knowledge for building the EPUB translation & voice-over web platform (epubtv). Auto-loaded during implementation work touching the FastAPI lifespan, alembic migration startup, or the `db_migrations` helper.
---

<context>
## Project: 2026-fwdays-agentic-greenfield-task (epubtv)

Hackathon-sprint web platform: EPUB translation + voice-over,
served by a single FastAPI container with in-process mocks.
Backend (Python + FastAPI + uv) owns the alembic migration startup
in the lifespan; frontend (TypeScript + Next.js static export +
yarn) consumes the same-origin API. The hexagonal architecture
binds four ports (translation / TTS / persistence / progress) on
`app.state` during the lifespan composition root.

Spike sessions wrapped: 2026-07-09 (001 — alembic fileConfig
silences lifespan logging)
</context>

<requirements>
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
</requirements>

<findings_index>
## Feature Areas

| Area | Reference | Key Finding |
|------|-----------|-------------|
| Lifespan startup logging | references/lifespan-startup-logging.md | `fileConfig` in `alembic/env.py:46` sets `disabled=True` on every logger not in `alembic.ini` `[loggers]` (epubtv + uvicorn both silenced) and resets root to WARNING. Fix: snapshot/restore logging state around the alembic call in `db_migrations.py`; optionally also pass `disable_existing_loggers=False` in `alembic/env.py`. Threading is irrelevant — the bug is process-global. |

## Source Files

Original spike source files are preserved in `sources/` for
complete reference. See
`sources/001-alembic-fileconfig-silences-logging/README.md` for
the full investigation trail and `experiments/` for the nine
reproducible scripts (baseline bug, sync-vs-thread, four fix
variants, end-to-end verification).
</findings_index>

<metadata>
## Processed Spikes

- 001-alembic-fileconfig-silences-logging (VALIDATED)
</metadata>
