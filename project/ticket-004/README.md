# Ticket 004: Live PostgreSQL QA target and storage engine report

- **ID**: ticket-004
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: EDIT
- **Created**: 2026-10-13

## Goal and scope

Integration part of the measured improvements the owner asked for on
2026-10-13 ("wykonaj"); the code is in ticket-003 (data-plane#13):

- `requirements-qa.txt`: `psycopg[binary]==3.3.6` for QA only;
- `Makefile`: opt-in `pg-live` target; it exits 2 without `DATA_PLANE_PG_DSN`;
- `docs/analysis/storage-engines.md`: SQLite, SQLite with group commit,
  PostgreSQL 16 and PGlite measured on one workload, the live schema result and
  the profile recommendations; indexed in `docs/README.md`.

`make pg-live` runs `tests.test_postgres_live`, so publish it after ticket-003.

## Acceptance criteria

- [x] AC-01: Scope is approved by a human owner (owner request 2026-10-13).
- [ ] AC-02: `make test` and `make check` behave as before without a database.
- [ ] AC-03: `./project/governance-check.sh` passes, including the docs gate.

## Tracking boundary

This directory contains the minimal reviewed intent.
