# Rebrander

Complete, verified rebrand of cloned software — from GitHub or website URLs to
a renamed, re-identified product — while keeping every usable feature intact.

**Values:** DRY · SRP · PRP (Plan-Refine-Propose) · RALPH (loop until done) ·
KISS · self-documenting function/class names with docstrings.

## Quick start

```bash
# Install (OpenCode + Claude Code)
bash install.sh

# Or run directly
python3 scripts/inventory.py --root <repo>
python3 scripts/brand-replace.py --brand brand.json --root <repo> --dry-run
```

## Workflow

1. **Intake** — clone sources, classify (repo / website / binary).
2. **Breakdown** — `inventory.py` seeds `ANALYSIS.md`; annotate each row.
3. **Brainstorm** — cross-repo feature matrix in `BRAINSTORM.md`.
4. **PRP gate** — draft `PLAN.md` with `brand-replace.py --dry-run`/`--diff`
   preview; stop for explicit approval.
5. **Execute** — `brand-replace.py --apply`, then metadata/UI/docs/assets/config
   passes; `gen-assets.py` for placeholders; `removal-log.py` for audit trail.
6. **RALPH loop** — build → test → lint → `artifact-scan.py` →
   `binary-diff.py` → repeat until green.
7. **Report** — `rubric-score.py` (0-100) + benchmark results.

## Script index

| Script | Purpose |
|---|---|
| `brand_tokens.py` | Shared token/variant logic (DRY) |
| `brand-replace.py` | Deterministic engine: `--dry-run` / `--diff` / `--apply` |
| `inventory.py` | Function/class inventory + coverage % |
| `artifact-scan.py` | Leftover-brand scan over built artifacts |
| `binary-diff.py` | DocIN `version_delta` pre/post diff |
| `rubric-score.py` | 0-100 rebrand quality scorecard |
| `gen-assets.py` | SVG wordmark/favicon/logo + theme swap |
| `benchmark.py` | Multi-repo pipeline benchmark (JSON + CSV) |
| `removal-log.py` | Attribution removal audit trail |
| `revert.py` | One-command revert via git |
| `rename-pack.py` | Per-stack rename dispatcher (ts-morph/LibCST/fallback) |

## Tests

```bash
PYTHONPATH=scripts python3 -m pytest tests/ -q
```

48 tests covering all scripts.

## License

See the repository's LICENSE file.
