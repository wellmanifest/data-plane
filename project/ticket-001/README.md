# Ticket 001: Adopt wellmanifest/new-project 0.20.97 governance

- **ID**: ticket-001
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-13

## Goal and scope

Install the published immutable `wellmanifest/new-project` package at
`c6587635bafb054241fd71fd22793af47acae83b` (0.20.97) through its adopter with
`--bootstrap-native-adoption`, so data-plane work is allocated through tickets
and the repository can later be enrolled for independent Validator publication.

The owner requested enrollment of data-plane and data-gateway in the
Wellmanifest fleet ("a i b", 2026-10-12). This ticket covers only the
governance package. Validator registry enrollment and the OneDev profile belong
to their owning repositories and need separate tickets.

The only repository-local change beyond installer bytes extends governance
ownership in `.governance/manifest.json` to `.gitattributes` and
`.github/workflows/new-project-branch-hygiene.yml`. The package installs both,
but its base manifest assigns them to no workstream. Product code, contracts,
schemas, protobuf and docs are out of scope.

## Acceptance criteria

- [ ] AC-01: Scope is approved by a human owner.
- [ ] AC-02: `create_adoption_lock.py --check` at the pinned revision reports no drift.
- [ ] AC-03: `./project/governance-check.sh` (against base `43b9519`), `make check` and `make test` pass.
- [ ] AC-04: Hosted checks pass on the PR head; publication follows the independent Validator, never the authoring agent.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
