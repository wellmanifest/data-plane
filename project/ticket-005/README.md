# ticket-005: Add a portable SQLite qualification schema and reproducible report template with adopter SLOs and evidence-based escalation rules for issue #16.

- **ID**: ticket-005
- **Owner**: agent:coding-agent
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal and scope

Supply issue #16's portable SQLite qualification contract as two additive profile artifacts: a machine-readable evidence/SLO schema with normative escalation rules and an explicitly unmeasured reproducible report template.

SESSION_EXECUTION_AUTHORIZATION: validated native ticket PLF-21585; Willman request fd416866-ba69-480d-a326-33781ffdc5bf; protected publication only.

## Acceptance criteria

- [x] AC-01: AC-01: The qualification schema names required read/write throughput; read/write transaction and lock-wait p50/p95/p99; SQLITE_BUSY counts/rates, retries and exhausted retries; writer-queue depth; WAL bytes/age and checkpoint age/backlog; CPU time per operation; logical/physical bytes per record; and host-load evidence. Metrics define units, populations, aggregation and collection methods. Measurement windows record start/end, duration, sampling interval, operation counts and warmup exclusion.
- [x] AC-02: AC-02: The schema-valid report template records workload identity, dataset size/record shape, read/write mix, storage class/device/filesystem/locality, OS/CPU/RAM, software and SQLite versions, source/base SHA, effective SQLite settings, reproducible invocation and seed, warmup, repetitions, client/process/host concurrency, host load, results and raw-evidence references. Unmeasured values are explicit placeholders, never fabricated measurements.
- [x] AC-03: AC-03: Adopter-configurable SLOs define throughput minima and applicable latency, contention, queue, WAL/checkpoint and resource maxima, with comparison operators, evaluation windows, minimum samples and persistence/retest policy. Missing thresholds, missing measurements or inadequate sampling produce not-evaluated/inconclusive outcomes. Templates and incomplete reports cannot claim qualification success.
- [x] AC-04: AC-04: Decision rules retain SQLite when representative measurements meet adopter SLOs; otherwise first apply bounded batching, bounded writer queues/backpressure and retesting while preserving durability. Consider data-gateway only for a demonstrated audit/idempotency contract need; PostgreSQL for persistent multi-process write contention or multi-host write requirements; Rust only when profiling demonstrates dominant application CPU cost. Eight clients and historical benchmark numbers are never universal thresholds.
- [x] AC-05: AC-05: Evidence and decision rules distinguish application CPU, SQLite lock contention, commit/fsync time, storage latency/saturation and external-provider latency through separately attributed spans/counters and profiling references. Host saturation and unavailable instrumentation are explicit. Unknown evidence cannot establish a bottleneck or justify unconditional migration or rewriting.
- [ ] AC-06: AC-06: Both artifacts preserve POA/CQRS/ES, WAL on same-host local storage, synchronous=FULL for durable acknowledged writes, foreign_keys=ON, one writer/authority per stream, fencing and authority-transfer requirements. Existing low-ram-v1 limits remain applicable, including bounded queues, batches, handles and memory measurement. Qualification grants no authority and cannot relax existing requirements.
- [x] AC-07: AC-07: Draft 2020-12 metaschema validation and offline template validation pass. Negative checks reject missing required sections and attempts to label unmeasured placeholders as measured or passing. Semantic review covers nested evidence requirements, SLO completeness, latency attribution and every escalation condition. Artifact validation does not claim live performance qualification.
- [ ] AC-08: AC-08: make check, make test and ./project/governance-check.sh pass in the eventual governed implementation checkout. The material implementation scope contains exactly the two frozen profile files, introduces no runtime dependencies and preserves existing standards, specifications, profiles, runtime behavior and managed adoption bytes.

## Implementation checkpoint (2026-10-31)

- Request: PLF-21585 / wellmanifest/data-plane#16; duplicate PLF-001 remains parked by admission.
- Frozen accepted base and observed HEAD: `f96048a4d3b3eb50e1269614eec65fd7092b1ac3`.
- Branch: `ticket/005-project-job-fd416866`; canonical worktree: `.worktrees/ticket-005--project-job-fd416866`.
- Runner lease: `allocation-ticket-005-project-job-fd416866`, revision 1, fencing token 1; observed owner `agent:coding-agent`, expiry `2026-10-31T15:53:13Z`. No lease takeover, renewal or release by this turn.
- Immutable intent SHA-256: `109a4621523f964353d4e2a08038f35be96cd2cc9f0df9a29d08840fd0d22230`; acceptedBaseSha already matches the frozen base.
- Work-start check: `REUSE_EXISTING`, no blockers; origin/main and local main observed at the frozen base (local refs only; no remote refresh).
- Recovery: the runner's primary-checkout index records checkpoint sequence 3 at `2026-10-31T13:53:17Z`. The linked checkout has no separate continuity stream (`GOV-CONTINUITY-002`); do not create another stream or change ignored carriers outside this turn's write scope. The runner owns the managed snapshot/checkpoint handoff.
- Scope: write only the two frozen profile artifacts and this README. Preserve the pre-existing index delta and immutable intent. No Git or external publication effects.
- Next action: implement and directly validate the additive schema/template. Broad conformance/governance and todo2code workspace comparison are reserved for the trusted runner, exactly once after this turn.

## Implementation evidence and runner handoff

Implemented exactly two additive material artifacts:

- `profiles/sqlite-qualification-v1.json`: self-contained Draft 2020-12 report schema, 48 named metrics with units/populations/aggregation/collection methods, explicit measurement windows and reproducibility metadata, adopter-owned SLOs and eight normative decision rules.
- `profiles/sqlite-qualification-report-v1.json`: matching schema-valid template. Every measurement/threshold is explicitly unmeasured/unconfigured, `status=template`, `qualification=not-evaluated`; no benchmark results or raw evidence are fabricated.

AC-01..05 and AC-07 are complete for artifact implementation and focused validation. AC-06's unchanged-contract portion is verified by an empty diff against the frozen base for `STANDARD.md`, `spec/**`, existing SQLite/low-RAM/POA profiles and `.governance/**`; its regression-test portion and AC-08 remain for the trusted runner. No runtime dependencies or behavior changed. The pre-existing two-row `project/TICKETS.md` delta belongs to admission and was preserved.

Focused results (2026-10-31T14:06:45Z):

- PASS: Draft 2020-12 metaschema validation and offline template validation with the pinned `jsonschema` dependency and `FormatChecker`.
- PASS: 1065 focused positive/negative and synthetic SLO-boundary checks. Coverage includes required top-level/nested fields and all metric evidence, rejection of measured/pass claims on the empty template, all measured metadata placeholders, missing SLO targets/results, WAL/FULL/foreign-key/single-writer/storage-locality invariants, metric type/range limits, review evidence, provider absence/applicability, gateway contract evidence, persistent multi-process/multi-host PostgreSQL routes and profiled application-CPU Rust preconditions. Synthetic cases existed only in memory and are not workload evidence.
- PASS: all schema `$ref` values resolve locally; metric, SLO and evaluation-result keys match. The final annotation clarifications were followed by metaschema/template/reference checks.
- PASS: synthetic comparisons exercise inclusive equality and just-over/under SLO boundaries. Cross-field arithmetic, ordered timestamps/quantiles, actual sample sufficiency, repetition coverage, configured persistence comparisons, evidence digests and bottleneck attribution remain explicit normative semantic-review obligations. JSON Schema validation and a claimed review boolean alone do not certify them. No runtime SLO evaluator was added.
- PASS: `git diff --check`, unchanged intent hash and accepted base, unchanged branch/HEAD, and observed current runner lease revision/fencing token 1/1.
- NOT RUN by explicit session instruction: `make check`, `make test`, `./project/governance-check.sh`, broad repository verification and todo2code compare-workspace. The trusted runner owns the authoritative gates exactly once after this turn. No live workloads, infrastructure, performance qualification or external publication were attempted.

Reproduce the focused artifact validation from the repository root:

```sh
python3 -B - <<'PYVALIDATE'
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
schema = json.loads(Path('profiles/sqlite-qualification-v1.json').read_text())
report = json.loads(Path('profiles/sqlite-qualification-report-v1.json').read_text())
Draft202012Validator.check_schema(schema)
Draft202012Validator(schema, format_checker=FormatChecker()).validate(report)
print('PASS qualification schema and unmeasured template')
PYVALIDATE
```

Final bounded checkpoint:

- Ticket/request: `ticket-005` / `PLF-21585` / `wellmanifest/data-plane#16`; status remains **IN_PROGRESS / PUBLICATION**.
- Plan: `artifact:project-plan/fd416866-ba69-480d-a326-33781ffdc5bf`, SHA-256 `4180256ea823e4463e83374f67b31bbf8bf1644e491d4c4952db25e17a98ce27`.
- Slice: `artifact:project-slice/fd416866-ba69-480d-a326-33781ffdc5bf`, ordinal 1/1, SHA-256 `e293dfcf13c06b8a1c07fc6d7dc7bec7d95108b3534288a88d92610792c08e09`.
- Worktree/branch/HEAD and immutable accepted base remain as recorded above; intent SHA-256 is unchanged.
- Lease remains runner-owned, revision 1 / fence 1, unexpired at final observation. No claim, renewal, release or publication-freeze change was made.
- Last observed managed checkpoint: `receipt:continuity.ticket-005.3.a6a812096568f845d21d5ba6bb469265ee4b36802b2eabef06f21b06c8f671bf`. Its runner snapshot predates these edits; this README does not claim a current managed snapshot or external receipt.
- Last runner remote/account receipt: `receipt:project-remote/fd416866-ba69-480d-a326-33781ffdc5bf`, observed `2026-10-31T13:53:17Z`; no new remote/account access was performed.
- Final schema SHA-256: `ec7872e5845f44731b532153e51c09afaa9f1c4bdefba979d181e54d9e229214`.
- Final template SHA-256: `dcb1ef697a9e3b4b51d810c1152bc9dad462574b99af2290d20ac78ceb07f02b`.
- Next action (runner): snapshot/checkpoint the final dirty workspace through its managed continuity route, run authoritative conformance/tests/governance exactly once, then perform its exact guarded publication. Revalidate unchanged intent/base, scope and fencing first. The model must not commit or invoke publication.

Delivery ledger:

- Completed: two scoped profile artifacts, focused artifact checks, semantic contract review and this evidence/handoff.
- Locally committed: none; no staging or commit was performed.
- Pushed / PR-open: none performed by this turn.
- Merged / deployed: none performed by this turn.
