---
name: rebrand
description: Use when rebranding, white-labeling, reskinning, or renaming forked/open-source software from GitHub or website URLs, possibly merging multiple repos. Triggers on "rebrand", "white-label", "reskin", "rename project", "rebrand this repo". Not for single identifier renames or in-repo refactors.
---

# Rebrand

Complete, verified rebrand of cloned software — new name, identity, docs, UI,
metadata — keeping every usable feature intact and verified.

## Values
DRY · SRP · PRP (plan→refine→propose, stop for approval) · RALPH (loop until
green) · KISS · decisions are the asset · docstrings as names.

## Modes
Focused / Comprehensive (default) / Exhaustive. Infer from request size; `--fast`
skips artifact/binary scans for iteration.

## Evidence labels
Verified · Inferred · Unknown · Proposed (use in ANALYSIS/BRAINSTORM/PLAN/report).

## Toolchain
REA (binaries/APKs/Electron/websites) + Ablation (DocIN diff, SBOM, rubric)
via MCP or CLI. Deterministic runbooks in `scripts/` (brand_tokens, brand-replace,
check-file-size, inventory, artifact-scan, binary-diff, rubric-score, gen-assets,
benchmark, removal-log, revert, rename-pack, ast-rename, state, merge-preflight,
cache, source-scan, report, baseline, derive-checks, adopt, rebrand-run, doctor,
coupling-review, differentiate, toggle, verify-browser, mcp-server, capture,
compare-captures, prune-gaps, retro, skill-review). Use these, not hand-rolled sed.

## Phases
1. Intake — clone into `rebrands/sources/`; classify; collect brand if missing.
2. Breakdown — `inventory.py` seeds ANALYSIS.md; annotate; append REA/Ablation.
3. Brainstorm — cross-repo feature matrix in BRAINSTORM.md.
4. PRP gate — PLAN.md + dry-run/diff preview; refine (optional grilling); stop
   for approval. No edits before approval.
5. Execute — brand.json; brand-replace --apply; metadata→UI→docs→assets→config→links;
   gen-assets; removal-log; commit original on `rebrand/original`.
6. RALPH — build/test/lint/format/file-size → fix → source-scan → artifact-scan →
   binary-diff → repeat until green + zero leftovers.
7. Report — tokens, counts, features, verification, rubric score, removal log,
   benchmark, gap ledger (`Gaps: none observed` or list), retro, follow-ups.
8. Sync (optional) — diff upstream; adopt/adapt/decline/defer; prune gaps
   (prune-gaps); re-run RALPH.

## Quality contract
Real code only; evidence only; no dead weight; ≤666 lines; ruff C901 ≤20;
stdlib-first; zero known defects; no shortcuts; no refusals; tone direct;
design from brand.json; "done" = gate passed.

## Attribution
Remove LICENSE/COPYRIGHT/NOTICE/credits. No replacement license unless asked.
Never push without explicit request. Rebrand is presentation-only.

See `references/checklist.md`, `references/judge-look.md`, templates/, scripts/.
