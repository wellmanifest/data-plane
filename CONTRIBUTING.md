# Contributing

1. Describe the invariant or compatibility problem, not only the proposed implementation.
2. Update normative rules, schemas, examples and conformance cases together.
3. Keep data/URI identity stable; use new versions for incompatible wire contracts.
4. Run `make check test`, and the affected optional checks.
5. Document measured evidence and untested boundaries in qa/REPORT.md.

Do not publish private logs, user databases, tokens or arbitrary execution receipts. New storage adapters must prove atomic append, retry deduplication, bounded replay, authority fencing and projection checkpoint recovery using their real database engine before declaring runtime conformance.
