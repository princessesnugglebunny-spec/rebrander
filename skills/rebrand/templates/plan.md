# Rebrand plan — <new brand>

> Proposed by Rebrander. **Awaiting confirmation — no files have been changed.**

## 1. Inputs
- Sources (status: cloned / needs-info):
  1.
- Target brand: name / slug / tagline / domain / colors
  (or open questions for the user)

## 2. What each source is
| Repo | Stack | Purpose | Key features |

## 3. Feature utilization (from BRAINSTORM.md)
| Feature | Source | Decision: headline / included / dropped | Rationale |

## 4. Structure decision
- [ ] Single merged product
- [ ] Per-source rebranded copies

Rationale:

## 5. Behavioral invariants (must not change)
What must remain identical after the rebrand:
- Public API signatures and return types
- CLI command names and output format
- Config file schema and defaults
- Test expectations (existing tests must still pass)
- Error messages structure (only brand strings change)

## 6. Integration differences
How the rebranded product wires into the target environment:
- Import paths / package names that consumers use
- Environment variables
- Default data/config/cache directories
- API endpoints / callback URLs
- Differences from upstream and how they are resolved

## 7. Exact asset inventory
| Asset | Source location | Replacement | Status |
|---|---|---|---|
| Logo (SVG) | assets/logo.svg | gen-assets.py placeholder | pending |
| Favicon | assets/favicon.ico | gen-assets.py placeholder | pending |
| Wordmark | — | gen-assets.py | pending |
| Theme colors | src/theme.css | brand.json colors | pending |

## 8. Acceptance cases
Specific scenarios to verify post-rebrand:
- [ ] CLI starts and responds to --help
- [ ] All existing tests pass
- [ ] No old-brand strings in source or artifacts
- [ ] New brand name appears in UI, docs, metadata
- [ ] Config files use new paths/names

## 9. Change scope (grouped, SRP passes)
1. Identifiers & namespaces —
2. Project metadata —
3. UI strings & theme —
4. Documentation —
5. Assets (placeholders where needed) —
6. Config / env / paths —
7. Links & URLs —

## 10. Dry-run preview (from brand-replace.py)
- Files that would change:
- Total replacements:
- Residual hits (manual review):
- Diff file:
- Inventory coverage:

## 11. Recommendations
Agent's recommendations for the rebrand approach, with rationale and
evidence from the analysis.

## 12. Open questions
Questions that must be answered before or during execution.

## 13. Verification plan (RALPH)
- Build / test / lint commands per source:
- Leftover-scan terms (old name variants, domain, org, package names):
- Artifact scan (REA/Ablation) for shipped binaries/bundles:
- Binary diff (DocIN) for binary builds:

## 14. Attribution removal
- LICENSE / COPYRIGHT / NOTICE / attribution files and headers to delete:

## 15. Risks
-

## 16. Approval
Reply with **approve** (or requested edits) to begin. Nothing is modified
before that.

## Small-change shortcut

If the rebrand change is a bounded unit (single file, no design question,
no new dependencies, lands in one place), skip the full PRP gate: implement
directly, preserve exact values and invariants, run a check, and report the
reference revision. If a design question comes up, stop and switch to the
full flow.
