"""Compile a final rebrand report (SRP: reporting only).

Gathers rubric score, removal-log scan, source-scan and optional baseline
into one markdown document for handoff.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent


def _run(args_list: List[str]) -> subprocess.CompletedProcess:
    """Run a script and return its completed process."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / args_list[0])] + args_list[1:],
        capture_output=True,
        text=True,
    )


def main() -> int:
    """Parse arguments and write the report."""
    parser = argparse.ArgumentParser(description="Compile a final rebrand report")
    parser.add_argument("--brand", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--artifacts", type=Path, default=None)
    parser.add_argument("--build-passed", action="store_true")
    parser.add_argument("--tests-passed", action="store_true")
    parser.add_argument("--inventory-coverage", type=float, default=0.0)
    parser.add_argument("--baseline", type=Path, default=None, help="baseline.json path")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    root = args.root
    # Rubric score.
    rubric_args = [
        "rubric-score.py",
        "--brand",
        str(args.brand),
        "--root",
        str(root),
        "--inventory-coverage",
        str(args.inventory_coverage),
        "--out",
        str(root / ".rubric-tmp.json"),
    ]
    if args.artifacts:
        rubric_args += ["--artifacts", str(args.artifacts)]
    if args.build_passed:
        rubric_args.append("--build-passed")
    if args.tests_passed:
        rubric_args.append("--tests-passed")
    _run(rubric_args)
    rubric = {}
    rp = root / ".rubric-tmp.json"
    if rp.exists():
        try:
            rubric = json.loads(rp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            rubric = {}
        rp.unlink(missing_ok=True)

    # Removal-log scan.
    rl_proc = _run(["removal-log.py", "--root", str(root), "--scan"])

    # Source scan.
    ss_proc = _run(
        ["source-scan.py", "--root", str(root), "--brand", str(args.brand), "--json", "--todo"]
    )
    try:
        ss = json.loads(ss_proc.stdout)
    except json.JSONDecodeError:
        ss = {}

    baseline = {}
    if args.baseline and args.baseline.exists():
        try:
            baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            baseline = {}

    lines = []
    lines.append("# Rebrand report")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## Rubric score")
    lines.append("")
    lines.append(f"- Score: {rubric.get('score', 'n/a')}/100 ({rubric.get('grade', '')})")
    for cat in rubric.get("categories", []):
        lines.append(f"  - {cat.get('name')}: {cat.get('score')}/{cat.get('max')}")
    lines.append("")
    lines.append("## Leftover scan")
    lines.append("")
    lines.append(f"- Brand hits: {len(ss.get('brand_hits', []))}")
    lines.append(f"- TODO hits: {len(ss.get('todo_hits', []))}")
    lines.append("")
    lines.append("## Attribution removal")
    lines.append("")
    lines.append("```")
    lines.append(rl_proc.stdout.strip())
    lines.append("```")
    lines.append("")
    if baseline:
        lines.append("## Baseline (before)")
        lines.append("")
        for k, v in baseline.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    lines.append("## Verification")
    lines.append("")
    lines.append(f"- Build passed: {args.build_passed}")
    lines.append(f"- Tests passed: {args.tests_passed}")
    lines.append(f"- Inventory coverage: {args.inventory_coverage}%")
    lines.append("")
    lines.append("## Gap ledger")
    lines.append("")
    gap_file = root / "rebrand-gaps.md"
    if gap_file.exists():
        lines.append(gap_file.read_text(encoding="utf-8").strip())
    else:
        lines.append("Gaps: none observed")
    lines.append("")

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
