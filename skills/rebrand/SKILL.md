---
name: Rebrand
description: Completely rebrand cloned software from GitHub or website URLs — clone and break down each source with an exhaustive function/feature inventory, brainstorm how to utilize as many features as possible, propose a plan for confirmation (PRP), then execute the rebrand and verify it in a loop (RALPH). Use when asked to rebrand, white-label, reskin, or rename forked/open-source software, possibly from multiple repos at once.
---

# Rebrand

Procedure for a complete, verified rebrand of one or more software sources.
The `rebrander` agent runs this workflow; any agent can load this skill to
follow the same procedure.

## Principles (apply throughout)

| Value | Meaning here |
| --- | --- |
| **DRY** | Brand tokens defined once in `brand.json`; every replacement derives from it |
| **SRP** | Each step/script does exactly one thing: inventory, rename, assets, docs, verify |
| **PRP** | Plan → Refine → Propose; no source edits until the user approves |
| **RALPH** | Loop: apply → build/test → fix → rescan until green with zero leftovers |
| **KISS** | Simplest mechanical change that achieves the rebrand; no refactors |
| **Decisions are the asset** | Brand tokens and design decisions matter more than mechanical renames; carry the encoded decisions, drop the packaging |
| **Docstrings as function and class names** | Self-documenting names, and a docstring on every function and class |

## Toolchain — REA + Ablation (part of the run)

Both tools are attached as OpenCode references (aliases `rea`, `ablation`);
read exact commands from those checkouts before use.

- **REA** (`morluto/rea` — "Reverse Engineer Anything") — inspect binaries,
  APKs, Electron/JS apps, and websites without source:
  - Intake/Breakdown: extract brand tokens and the feature inventory for
    inputs with no source repo — every finding evidence-backed.
  - Brainstorm: its "understand a feature → rebuild it" flow grounds the
    feature-utilization plan in how the original works.
  - Verify: scan built artifacts/bundles for leftover old-brand strings that
    source grep cannot see.
  - Prefer MCP when registered (`npx rea-agents setup` does it — interactive,
    offer it); otherwise CLI: `npx -y rea-agents@latest <command>`.
- **Ablation** (`Ablation-Tool/ablation` — "ABL∀TION" AI-assisted reverse
  engineering framework):
  - Intake/Breakdown: recover embedded brand strings, endpoints, and
    function inventories from binaries/firmware (`ablation --help`;
    `pip install ablation-tool`).
  - Verify: DocIN binary diffing (pre- vs post-rebrand build) proves only
    branding changed; SBOM/finding exports (JSON/SARIF) feed the report.
  - Quality gate: the Rubric Library (`docs/prompts/analysis-rubric.md`)
    scores the rebrand before reporting done.
- **Deterministic runbooks** (ship in this skill's `scripts/` — use these
  instead of hand-rolled sed so replacements and scans are reproducible):
  - `brand_tokens.py` — shared token/variant logic (DRY).
  - `brand-replace.py` — `--dry-run` / `--diff` / `--apply` engine driven
    by brand.json.
  - `inventory.py` — function/class inventory with coverage %.
  - `artifact-scan.py` — leftover-brand scan over built artifacts (with
    optional `ablation analyze` deep pass).
  - `binary-diff.py` — DocIN `version_delta` pre/post diff (needs
    `ablation-tool[full]`).
  - `rubric-score.py` — 0-100 rebrand quality scorecard (build/tests/
    leftovers/attributions/inventory/docs/assets).
  - `gen-assets.py` — SVG wordmark/favicon/logo placeholders + theme
    color swap.
  - `benchmark.py` — run the pipeline on N repos and report metrics.
  - `removal-log.py` — attribution removal audit trail (`--scan` or log).
  - `revert.py` — one-command revert via git (snapshot-per-attempt).
  - `rename-pack.py` — per-stack rename dispatcher (ts-morph/LibCST when
    available, regex fallback otherwise).
  - `ast-rename.py` — Python AST-aware identifier renamer (stdlib ast,
    no dependencies).
- Not installed or not registered → say so in the plan and offer setup;
  never silently skip these steps when the target type needs them.

## Phases

### 1. Intake
- Inputs: GitHub URL(s) and/or website URL(s). Unwrap redirect wrappers
  (Google `/url?q=...`, etc.) to get the real target first.
- Website URL → fetch it and locate the source (repo link, download,
  registry). No source found → ask the user, never guess.
- Clone all sources into `rebrands/sources/<repo-name>`.
- Collect the target brand (name, tagline, colors, domain) if not given;
  fold open questions into the plan proposal.
- Classify each input (source repo / website / binary-or-app artifact); no-
  source inputs go through REA — Ablation for binaries — for brand tokens
  and features before anything else.

### 2. Breakdown & inventory (per source)
- Stack, architecture, entry points, build/test/lint commands, directory map.
- Exhaustive inventory of every public function, class, CLI command, config
  option, integration, and user-facing feature:

  | Feature / function | Kind | Location | Description | Rebrand impact |
- Large or multiple repos: parallel `explore` subagents.
- Run `scripts/inventory.py --root <repo>` first to seed ANALYSIS.md, then
  annotate each row with a one-line description and rebrand impact.
- Output: `rebrands/ANALYSIS.md` (one section per source). No-source
  targets: append REA/Ablation findings, each with its evidence pointer.

### 3. Brainstorm — utilize as many features as possible
- Cross-repo feature matrix: for each feature decide headline / combine /
  redundant / drop, with rationale.
- Decide structure: one merged product vs. per-source rebranded copies.
- Rank by value vs. effort — KISS favors the simple path to maximum feature
  coverage.
- Output: `rebrands/BRAINSTORM.md`.

### 4. PRP — propose and wait
- **Plan**: write `rebrands/PLAN.md` from `templates/plan.md`.
- **Dry-run preview**: when brand tokens are drafted, run
  `scripts/brand-replace.py --brand brand.json --root <repo> --dry-run` and
  `--diff`, and attach the file counts, residual-hit list, and diff to
  PLAN.md so approval is based on the actual change set.
- **Refine**: check against ANALYSIS, BRAINSTORM, and user answers until no
  blocking question remains.
- **Propose**: present in chat, ask for explicit approval, **stop**. Nothing
  is modified before approval.

**Small-change shortcut**: if the change is a bounded unit (single file, no
design question, no new dependencies), skip the full gate — implement
directly, preserve exact values and invariants, run a check, report. If a
design question comes up, stop and switch to the full flow.

### 5. Execute (only after approval)
- Create `brand.json` (DRY source of truth: name, slug, package prefix,
  namespace, domain, colors, tagline).
- Apply identifier renames with `scripts/brand-replace.py --apply`; do the
  metadata, UI strings/theme, docs, assets, config/env, and link passes by
  hand (context-specific).
- Run `scripts/gen-assets.py --brand brand.json --root <repo> --swap-colors`
  for SVG wordmark/favicon/logo placeholders and theme color swap.
- Run `scripts/removal-log.py --root <repo> --removed <files...>` to record
  the attribution removal audit trail (or `--scan` to verify clean).
- Snapshot safety: commit the original on `rebrand/original` before edits;
  `scripts/revert.py` restores it in one command if a pass goes wrong.
- Mechanical replacements only (KISS). Remove original license/attribution
  files, headers, and credits. Keep touched names self-documenting with
  docstrings.

### 6. RALPH verification loop
build + tests + lint → fix failures → source leftover scan for old-brand
tokens (all case/separator variants, old domain, old org/user, old package
names) → artifact scan via REA/Ablation for shipped binaries/bundles, with
the DocIN binary diff proving branding-only changes → repeat until
everything passes and both scans are zero (attribution files have been
removed; brand.json is exempt as the token manifest).

### 7. Report
Brand tokens applied, change counts per category, features carried over,
verification + leftover-scan results, the rubric score from
`scripts/rubric-score.py` (0-100), removal log, and follow-ups (publishing,
real logo assets). For multi-repo runs, `scripts/benchmark.py` produces the
comparison report.

Update `rebrand-gaps.md` with any features not yet carried over, pending
changes, or declined items (so they are not re-raised on next sync).

### 8. Rebrand sync (optional, post-release)
Periodically check if source repos have changed:
1. Diff source repos against `rebrands/sources/` clones.
2. Classify each upstream change: adopt / adapt / decline / defer.
3. Record in `rebrand-gaps.md` with evidence.
4. Apply adopted/adapted changes through the spec's adaptations (not patches).
5. Re-run the RALPH loop.

## Supporting files
- `references/checklist.md` — exhaustive rebrand checklist; run it before
  declaring done.
- `templates/plan.md` — plan/proposal template for the PRP gate.
- `templates/brand.json` — brand token schema template.
- `templates/brand.schema.json` — JSON Schema for brand.json validation.
- `scripts/` — deterministic runbooks (see above).
- `tests/` — 50 pytest tests covering all scripts.
- `README.md` — package entry point.
- `LICENSE` — MIT.
