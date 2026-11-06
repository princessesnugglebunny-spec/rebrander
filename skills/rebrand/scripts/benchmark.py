#!/usr/bin/env python3
"""Benchmark harness (P1): run the rebrand pipeline on multiple repos and report.

For each repo path given, runs inventory -> brand-replace dry-run -> apply ->
artifact scan -> rubric score, collecting metrics. Produces a JSON/CSV report
so rebrand quality can be tracked and compared across runs (and across the
three reference repos: ablation, rea, code-distilling).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt

SCRIPTS = Path(__file__).resolve().parent


def run_script(name: str, args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name)] + args,
        capture_output=True, text=True, check=False,
    )


def benchmark_repo(repo: Path, brand: Path, work_copy: Path) -> Dict:
    """Run the pipeline on one repo; return metrics dict."""
    metrics: Dict = {"repo": str(repo), "status": "ok"}
    t0 = time.time()

    # 1. Copy repo to a work copy (don't mutate the source).
    if work_copy.exists():
        shutil.rmtree(work_copy)
    shutil.copytree(repo, work_copy, ignore=shutil.ignore_patterns(".git"))

    # 2. Inventory.
    r = run_script("inventory.py", ["--root", str(work_copy), "--json"])
    inv = {}
    try:
        inv = json.loads(r.stdout)
    except json.JSONDecodeError:
        metrics["inventory_error"] = r.stderr.strip() or r.stdout[:200]
    metrics["inventory_coverage"] = inv.get("coverage_percent", 0.0)
    metrics["definitions_total"] = inv.get("definitions_total", 0)
    metrics["files_scanned"] = inv.get("files_scanned", 0)

    # 3. Dry-run (pre-apply).
    r = run_script("brand-replace.py", ["--brand", str(brand), "--root", str(work_copy),
                                        "--dry-run", "--json"])
    dry = {}
    try:
        dry = json.loads(r.stdout)
    except json.JSONDecodeError:
        metrics["dryrun_error"] = r.stderr.strip() or r.stdout[:200]
    metrics["dryrun_files_changed"] = dry.get("files_changed", 0)
    metrics["dryrun_total_replacements"] = dry.get("total_replacements", 0)
    metrics["dryrun_residual_files"] = len([
        f for f in dry.get("files", []) if f.get("residual_lines")
    ])

    # 4. Apply.
    r = run_script("brand-replace.py", ["--brand", str(brand), "--root", str(work_copy),
                                        "--apply", "--json"])
    applied = {}
    try:
        applied = json.loads(r.stdout)
    except json.JSONDecodeError:
        metrics["apply_error"] = r.stderr.strip() or r.stdout[:200]
    metrics["applied_files_changed"] = applied.get("files_changed", 0)
    metrics["applied_total_replacements"] = applied.get("total_replacements", 0)

    # 5. Post-apply dry-run (should be clean).
    r = run_script("brand-replace.py", ["--brand", str(brand), "--root", str(work_copy),
                                        "--dry-run", "--json"])
    post = {}
    try:
        post = json.loads(r.stdout)
    except json.JSONDecodeError:
        pass
    metrics["post_apply_residual_files"] = len([
        f for f in post.get("files", []) if f.get("residual_lines")
    ])

    # 6. Artifact scan (on work_copy, treating it as artifacts).
    r = run_script("artifact-scan.py", ["--brand", str(brand), "--artifacts", str(work_copy),
                                        "--json"])
    art = {}
    try:
        art = json.loads(r.stdout)
    except json.JSONDecodeError:
        pass
    metrics["artifact_files_with_hits"] = art.get("files_with_hits", 0)

    # 7. Rubric score.
    r = run_script("rubric-score.py", ["--brand", str(brand), "--root", str(work_copy),
                                       "--inventory-coverage", str(metrics["inventory_coverage"]),
                                       "--out",
                                       str(work_copy / ".rubric.json")])
    # rubric-score doesn't support --json for stdout; read the file.
    rubric_path = work_copy / ".rubric.json"
    if rubric_path.exists():
        try:
            rubric = json.loads(rubric_path.read_text())
            metrics["rubric_total"] = rubric.get("total_score", 0)
            metrics["rubric_grade"] = rubric.get("grade", "?")
        except json.JSONDecodeError:
            metrics["rubric_total"] = -1
    else:
        metrics["rubric_total"] = -1
        metrics["rubric_error"] = r.stderr.strip() or r.stdout[:200]

    metrics["elapsed_seconds"] = round(time.time() - t0, 2)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebrand pipeline benchmark")
    parser.add_argument("--repos", nargs="+", required=True, help="repo paths to benchmark")
    parser.add_argument("--brand", required=True, type=Path, help="brand.json to apply")
    parser.add_argument("--workdir", default="/tmp/opencode/bench", type=Path,
                        help="scratch directory for work copies")
    parser.add_argument("--out", default="benchmark-report.json", type=Path,
                        help="output report path")
    parser.add_argument("--csv", action="store_true", help="also write CSV summary")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    args.workdir.mkdir(parents=True, exist_ok=True)
    brand = bt.load_brand(args.brand)

    results = []
    for i, repo_str in enumerate(args.repos):
        repo = Path(repo_str).resolve()
        if not repo.exists():
            results.append({"repo": str(repo), "status": "not found"})
            continue
        work_copy = args.workdir / f"repo-{i}"
        print(f"[{i+1}/{len(args.repos)}] Benchmarking {repo.name} ...", flush=True)
        try:
            m = benchmark_repo(repo, args.brand, work_copy)
            results.append(m)
            print(f"    score={m.get('rubric_total', '?')}  "
                  f"replacements={m.get('applied_total_replacements', '?')}  "
                  f"residual={m.get('post_apply_residual_files', '?')}  "
                  f"elapsed={m.get('elapsed_seconds', '?')}s")
        except Exception as exc:  # noqa: BLE001
            results.append({"repo": str(repo), "status": "error", "error": str(exc)})
            print(f"    ERROR: {exc}")

    report = {
        "brand": str(args.brand),
        "repos_benchmarked": len(results),
        "results": results,
    }
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport written to {args.out}")

    if args.csv:
        csv_path = args.out.with_suffix(".csv")
        fieldnames = ["repo", "status", "inventory_coverage", "definitions_total",
                      "dryrun_total_replacements", "applied_total_replacements",
                      "post_apply_residual_files", "artifact_files_with_hits",
                      "rubric_total", "rubric_grade", "elapsed_seconds"]
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for r in results:
                w.writerow(r)
        print(f"CSV written to {csv_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
