# Changelog

## Unreleased

- Conformance image pinned to the python:3.12-slim index digest so builds are reproducible.
- Reference gateway for line/v1 published as wellmanifest/data-gateway — [opis](docs/information/line-format.md).
- `error:` lines now have a closed reference mapping limited to adopter catalog codes — [opis](docs/information/line-format.md).
- New `data-plane.line/v1`: one line `type: target {vars}` for requests, results and event logs across shell, REST, gRPC and MCP — [opis](docs/information/line-format.md).
- `make docs-check` runs the pinned docs gate with negative canaries in the conformance workflow (advisory until required) — [opis](docs/information/docs-report-logs-adoption.md).
- Pinned wellmanifest/docs 0.1.1 and added a docs index; final reports now use docs placement plus a report manifest — [opis](docs/information/docs-report-logs-adoption.md).

## 0.2.0 — 2026-10-09

- POA/CQRS/ES required for every deployment profile.
- Domain event store separated from canonical wellmanifest/logs 0.5.0 audit.
- Pinned upstream contract, Protobuf and checker with exact SHA-256.
- SQLite embedded and hybrid coexistence profiles; one writer per stream, relay and authority-transfer rules.
- Low-RAM default; Redis optional and off initially.
- Multi-source GraphQL query policy and executable two-source fixture.
- New /v2 operation URIs; 11 contract operations including plan, event read and projection status.
- PostgreSQL ES schema, typed domain Protobuf and bounded SQLite ES conformance model.
- Added Makefile, Docker/Compose, CI, contributor instructions and RAM probe.

### Upgrade from 0.1

Do not silently reinterpret /v1 mutations. Introduce /v2, event capture and baseline import. Existing entity/process tables become projections. Keep SQLite until all writers and replay are verified. Changing sourceOfTruth to ES is an application migration, not merely updating manifest.json. The old postgres-redis-v1 profile is superseded; select a storage profile and optional redis-cache-v1 explicitly.

## 0.1.0

Initial PostgreSQL/Redis gateway proposal, eight operation contracts and SQLite audit tool. It did not require a full domain event store.
