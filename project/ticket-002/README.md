# Ticket 002: Assign data-plane source paths to workstreams

- **ID**: ticket-002
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-13

## Goal and scope

After governance adoption (ticket-001), most tracked data-plane paths are owned
by no workstream, so no product ticket can be allocated for them. This ticket
extends only the target-owned `.governance/manifest.json`:

- application: `conformance/**`, `benchmarks/**`, `reference/**`;
- integration: the standard text and `spec/**`, `contracts/**`, `schemas/**`,
  `profiles/**`, `examples/**`, `errors/**`, the error catalog, `manifest.json`,
  `upstream.lock.json`, `requirements-qa.txt`, `Makefile`, `tools/**`, `qa/**`,
  `SOURCES.md`, `NOTICE`, `LLM_REFACTORING.md`;
- infrastructure: `.dockerignore`, `.github/workflows/conformance.yml`.

It is a prerequisite for the measured improvements the owner asked for on
2026-10-13 ("wykonaj"): faster `canonical()`, the live PostgreSQL schema test
and the storage-engine benchmark.

## Acceptance criteria

- [x] AC-01: Scope is approved by a human owner (owner request 2026-10-13).
- [ ] AC-02: Every tracked path has exactly one owner; `./project/governance-check.sh` passes.

## Tracking boundary

This directory contains the minimal reviewed intent.
