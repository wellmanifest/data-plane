# ticket-001 — agent notes (claude)

## Route

1. Fresh clone of `main` at `8eeafd4` (after data-plane #7 Docker pin and #8 CONTRIBUTING removal).
2. Untracked prerequisites `TODO.md`, `project/TICKETS.md`.
3. `create_adoption_lock.py --source-revision c6587635… --bootstrap-native-adoption --upgrade` in the primary clone, which wrote `.subactor/receipts/bootstrap-adoption.json`.
4. `work_start_check.py --allocation-check` returned `RECONCILE` / `pending-delta` with dirtyDigest `576732b9…`.
5. `./project/new-ticket.sh -w governance --path … --bootstrap-adoption-digest 576732b9…` allocated ticket-001 in its canonical worktree.
6. Same adopter `--upgrade` applied in this worktree; the file set matches the primary delta plus the ticket directory.

## Deviations recorded

- **Duplicate `TODO.md` in allowedPaths.** The bootstrap branch of `new-ticket.sh` (line 928) prepends `TODO.md` and appends `--path` values without de-duplication. `string_list` then rejects the intent with GOV-INTENT-002. The duplicate was removed by hand.
- **Lease `scopeHash`.** The allocator projection lease in `.subactor/leases/` was computed over the original list. It is advisory local state, not a controller grant (allocator comment), and the gate does not compare it. No controller lease was issued or fabricated.
- **Unowned installer files.** The base manifest at 0.20.97 owns neither `.gitattributes` nor `new-project-branch-hygiene.yml`, which gave GOV-SCOPE-001/GOV-WORKSTREAM-003. Governance ownership was extended in the target-owned `.governance/manifest.json`, as nl-uri-dsl-llm and how-to-use-subactor did.

## Checks

Results are recorded in the PR description with the exact commands that ran.
