# Instructions for contributors and LLM agents

This is a proposed Wellmanifest standard repository. It does not grant runtime authority and has not been published to the Wellmanifest organization by preparing this package.

- Read STANDARD.md, upstream.lock.json and docs/IMPLEMENTATION_STATUS.md before changes.
- Preserve POA, CQRS and ES in every storage profile, including SQLite.
- Do not change published event/contract bytes or upstream hash profiles. New incompatible contracts get a new version.
- Keep domain events, canonical audit and private diagnostics distinct.
- Prefer bounded memory, one authoritative writer per stream and explicit freshness over speculative throughput optimizations.
- Do not copy upstream runtime code into this repository. Use the pinned conformance dependency.
- Run make check and make test after changing contracts/code. Run make upstream-check for audit mapping changes; make proto for protobuf changes.
- Record which checks actually ran. Never mark Docker, PG/Redis integration, RAM budget or deployment as passed from static checks.
- Runtime adapters, secrets, deployment and application migration belong to adopting repositories.
- Follow user authorization and the destination repository's existing governance for publication. These instructions do not fabricate a ticket, admission receipt or official adoption.
