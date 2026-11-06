# Rebrand gaps ledger

Tracks features from source repos not yet carried over, pending rebrand
changes, and declined changes (so they are not re-raised on next sync).

Each gap has an evidence pointer and a proposed treatment. Declined gaps
are recorded so they are not raised again.

## Format

| ID | Source | Gap (what's missing/drifted/unverified) | Evidence | Treatment | Status |
|---|---|---|---|---|---|
| G1 | repo-a | Feature X not ported | src/x.py:42 | adopt / adapt / decline / defer | open |

## Treatments

- **adopt** — carry the feature/fix into the rebranded product as-is.
- **adapt** — carry it but re-express in the rebranded product's conventions.
- **decline** — do not carry it; record reason so it is not re-raised.
- **defer** — acknowledge but postpone to a later iteration.

## Rules

- Every gap must cite evidence (file, function, commit, or test).
- Declined gaps are never re-raised unless the evidence changes.
- Gaps that change the spec go through the PRP review gate before code changes.
- Small catch-ups (unambiguous adoptions like upstream bug fixes) can be
  applied directly without the full gate.
- After a gap is closed, mark status `closed` with the commit/PR reference.

## Sync workflow

1. Diff source repos against the clones recorded in `rebrands/sources/`.
2. For each upstream change, classify: adopt / adapt / decline / defer.
3. Record in this ledger with evidence.
4. Apply adopted/adapted changes through the spec's adaptations (not as patches).
5. Update the spec if a gap changes the contract.
6. Re-run the RALPH loop.
