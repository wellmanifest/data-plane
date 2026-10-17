# Ticket 003: Faster canonical event hashing, single line parse and storage engine benchmark

- **ID**: ticket-003
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: EDIT
- **Created**: 2026-10-13

## Goal and scope

Application part of the measured improvements the owner asked for on
2026-10-13 ("wykonaj"), found while benchmarking the data-gateway pilot:

- `conformance/event_store.py`: `canonical()` walks the value with an explicit
  stack instead of recursion. Output bytes, key order and errors are unchanged;
  hashing an event is about 17% faster.
- `conformance/line.py`: `line_to_request(text, contracts=None, *, parsed=None)`
  reuses a line the caller already parsed (data-gateway parsed each line four
  times).
- `tests/test_canonical_equivalence.py`: 20 000 random structures compared with
  the previous recursive implementation, including error cases.
- `tests/test_postgres_live.py`: applies `examples/postgres/es-schema.sql` to a
  disposable PostgreSQL and checks RLS isolation, immutable history, unique
  stream versions and the guarded head CAS. Skipped unless `DATA_PLANE_PG_DSN`
  is set and psycopg is installed.
- `benchmarks/engines.py`: the same command/query workload on SQLite, SQLite
  with group commit, PostgreSQL and PGlite.

The QA dependency, `make pg-live` and the analysis report go in a separate
integration ticket.

## Acceptance criteria

- [x] AC-01: Scope is approved by a human owner (owner request 2026-10-13).
- [ ] AC-02: `canonical()` matches the previous implementation on every generated case.
- [ ] AC-03: `make test` passes without a database or psycopg.
- [ ] AC-04: The live PostgreSQL test passes against PostgreSQL 16 (3/3 on 2026-10-13).
- [ ] AC-05: `./project/governance-check.sh` passes.

## Tracking boundary

This directory contains the minimal reviewed intent.
