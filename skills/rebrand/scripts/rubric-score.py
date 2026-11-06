#!/usr/bin/env python3
"""Rebrand quality scorecard (P1 differentiator).

Evaluates a completed rebrand across measurable criteria and emits a 0-100
score with per-criterion breakdown. Complements the Ablation Rubric Library
(LLM behavior specs) with deterministic, reproducible metrics so the rebrand
can be tracked and compared across runs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "target", "dist", "build", ".next"}


def run_brand_replace_dry(brand: Path, root: Path) -> Tuple[int, int, List[str]]:
    """Return (files_changed, total_replacements, residual_files)."""
    import subprocess as sp
    script = Path(__file__).resolve().parent / "brand-replace.py"
    r = sp.run(
        [sys.executable, str(script), "--brand", str(brand), "--root", str(root),
         "--dry-run", "--json"],
        capture_output=True, text=True, check=False,
    )
    if r.returncode not in (0, 1):
        return -1, -1, [f"error: {r.stderr.strip()}"]
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return -1, -1, [f"parse error: {r.stdout[:200]}"]
    residual_files = [
        f["file"] for f in data.get("files", []) if f.get("residual_lines")
    ]
    return data.get("files_changed", 0), data.get("total_replacements", 0), residual_files


def count_attribution_files(root: Path) -> List[str]:
    """Find LICENSE/COPYRIGHT/NOTICE/attribution files still present."""
    names = {"LICENSE", "LICENSE.md", "LICENSE.txt", "COPYRIGHT", "COPYRIGHT.md",
             "NOTICE", "NOTICE.md", "THIRD_PARTY_NOTICES.md", "THIRD-PARTY-NOTICES"}
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in names or fn.upper().startswith("LICENSE") or fn.upper().startswith("COPYRIGHT"):
                found.append(str(Path(dirpath).relative_to(root) / fn))
    return found


def check_docs_clean(root: Path, original_tokens: List[str]) -> Tuple[bool, int]:
    """Check .md files for leftover old-brand tokens. Returns (clean, hit_count)."""
    variants = bt.residual_variants(original_tokens)
    hits = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            full = Path(dirpath) / fn
            try:
                text = full.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            for v in variants:
                if v in text:
                    hits += 1
                    break
    return hits == 0, hits


def check_assets(root: Path) -> Tuple[bool, List[str]]:
    """Check for logo/favicon/wordmark placeholders."""
    found = []
    asset_names = {"logo.svg", "favicon.svg", "wordmark.svg", "logo.png",
                   "favicon.ico", "icon.svg"}
    for dirpath, _dn, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower() in asset_names or "logo" in fn.lower() or "favicon" in fn.lower():
                found.append(fn)
    return len(found) > 0, found


def check_theme_colors(root: Path, target_colors: Dict) -> Tuple[bool, int]:
    """Check if target brand colors appear in CSS/theme files."""
    if not target_colors:
        return True, 0
    color_vals = [str(v).lower() for v in target_colors.values() if isinstance(v, str)]
    found_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not (fn.endswith(".css") or fn.endswith(".scss") or fn.endswith(".less")
                    or fn.endswith(".json") or fn.endswith(".yaml") or fn.endswith(".yml")):
                continue
            full = Path(dirpath) / fn
            try:
                text = full.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            for c in color_vals:
                if c in text:
                    found_count += 1
                    break
    return found_count > 0, found_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebrand quality scorecard")
    parser.add_argument("--brand", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path, help="rebranded source root")
    parser.add_argument("--artifacts", type=Path, help="built-artifact directory (optional)")
    parser.add_argument("--build-passed", action="store_true", help="build passed")
    parser.add_argument("--tests-passed", action="store_true", help="tests passed")
    parser.add_argument("--inventory-coverage", type=float, default=0.0,
                        help="coverage %% from inventory.py (0-100)")
    parser.add_argument("--out", type=Path, help="write JSON scorecard to file")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    brand = bt.load_brand(args.brand)
    original_tokens = list(brand.get("original", {}).values())
    target = brand.get("target", {})
    target_colors = target.get("colors", {})

    # Criterion 1: Brand completeness (20 pts)
    token_keys = ("name", "slug", "org", "package", "namespace")
    present_keys = sum(1 for k in token_keys if k in brand.get("original", {}) and k in target)
    brand_complete_score = int((present_keys / len(token_keys)) * 10)
    files_changed, total_replacements, residual_files = run_brand_replace_dry(args.brand, args.root)
    if residual_files:
        brand_complete_score = max(0, brand_complete_score - 5)
    if files_changed == 0 and total_replacements == 0:
        brand_complete_score += 10  # clean rebrand (no leftover tokens)
    brand_complete_score = min(20, brand_complete_score)

    # Criterion 2: Feature preservation (20 pts)
    feature_score = 0
    if args.build_passed:
        feature_score += 10
    if args.tests_passed:
        feature_score += 10

    # Criterion 3: Leftover scan (20 pts)
    leftover_score = 20
    if residual_files:
        leftover_score -= min(15, len(residual_files) * 3)
    # Artifact scan
    artifact_clean = True
    if args.artifacts and args.artifacts.exists():
        import subprocess as sp
        script = Path(__file__).resolve().parent / "artifact-scan.py"
        r = sp.run(
            [sys.executable, str(script), "--brand", str(args.brand),
             "--artifacts", str(args.artifacts), "--json"],
            capture_output=True, text=True, check=False,
        )
        try:
            adata = json.loads(r.stdout)
            if adata.get("files_with_hits", 0) > 0:
                artifact_clean = False
                leftover_score -= min(10, adata["files_with_hits"] * 2)
        except json.JSONDecodeError:
            pass
    leftover_score = max(0, leftover_score)

    # Criterion 4: Attribution removal (10 pts)
    attr_files = count_attribution_files(args.root)
    attr_score = 10 if not attr_files else max(0, 10 - len(attr_files) * 2)

    # Criterion 5: Inventory coverage (10 pts)
    inv_score = min(10, int(args.inventory_coverage / 10))

    # Criterion 6: Documentation (10 pts)
    docs_clean, docs_hits = check_docs_clean(args.root, original_tokens)
    docs_score = 10 if docs_clean else max(0, 10 - docs_hits * 2)

    # Criterion 7: Assets/theme (10 pts)
    assets_exist, asset_list = check_assets(args.root)
    theme_ok, theme_count = check_theme_colors(args.root, target_colors)
    asset_score = 0
    if assets_exist:
        asset_score += 5
    if theme_ok:
        asset_score += 5

    total = (brand_complete_score + feature_score + leftover_score +
             attr_score + inv_score + docs_score + asset_score)

    scorecard = {
        "total_score": total,
        "max_score": 100,
        "grade": _grade(total),
        "criteria": {
            "brand_completeness": {"score": brand_complete_score, "max": 20,
                                   "detail": f"{present_keys}/{len(token_keys)} token keys; "
                                             f"residual files: {len(residual_files)}"},
            "feature_preservation": {"score": feature_score, "max": 20,
                                     "detail": f"build={'pass' if args.build_passed else 'fail/unknown'}, "
                                               f"tests={'pass' if args.tests_passed else 'fail/unknown'}"},
            "leftover_scan": {"score": leftover_score, "max": 20,
                              "detail": f"source residual files: {len(residual_files)}; "
                                        f"artifact clean: {artifact_clean}"},
            "attribution_removal": {"score": attr_score, "max": 10,
                                    "detail": f"remaining attribution files: {len(attr_files)} "
                                              f"{attr_files[:5]}"},
            "inventory_coverage": {"score": inv_score, "max": 10,
                                   "detail": f"coverage: {args.inventory_coverage:.1f}%"},
            "documentation": {"score": docs_score, "max": 10,
                              "detail": f"md files with old tokens: {docs_hits}"},
            "assets_theme": {"score": asset_score, "max": 10,
                             "detail": f"assets found: {len(asset_list)}; theme colors applied: {theme_ok}"},
        },
        "inputs": {
            "build_passed": args.build_passed,
            "tests_passed": args.tests_passed,
            "inventory_coverage": args.inventory_coverage,
            "artifacts_scanned": bool(args.artifacts and args.artifacts.exists()),
        },
    }

    if args.out:
        args.out.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
        print(f"Scorecard written to {args.out}")

    # Human-readable summary
    print("=" * 60)
    print(f"  REBRAND SCORE: {total}/100  (Grade: {_grade(total)})")
    print("=" * 60)
    for name, c in scorecard["criteria"].items():
        bar = "#" * (c["score"] * 2) + "." * ((c["max"] - c["score"]) * 2)
        print(f"  {name:24s} {c['score']:2d}/{c['max']:<2d}  [{bar}]")
        print(f"  {'':24s}   {c['detail']}")
    print("=" * 60)
    return 0


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


if __name__ == "__main__":
    sys.exit(main())
