# Contributing

1. Describe the invariant or compatibility problem, not only the proposed implementation.
2. Update normative rules, schemas, examples and conformance cases together.
3. Keep data/URI identity stable; use new versions for incompatible wire contracts.
4. Run `make check test`, and the affected optional checks.
5. Document measured evidence and untested boundaries in a docs/analysis/<id>.md report with its .report.json manifest (see [docs/information/docs-report-logs-adoption.md](docs/information/docs-report-logs-adoption.md)); raw outputs stay under qa/. The 0.2.0 qa/REPORT.md is retained as a historical record.

Do not publish private logs, user databases, tokens or arbitrary execution receipts. New storage adapters must prove atomic append, retry deduplication, bounded replay, authority fencing and projection checkpoint recovery using their real database engine before declaring runtime conformance.
