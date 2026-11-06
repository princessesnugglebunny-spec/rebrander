#!/usr/bin/env python3
"""Multi-repo merge conflict preflight (Tier 3).

When the brainstorm decides on a 'merged product', this script checks for
colliding file paths and duplicate definitions across source trees before
any merge happens.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt


def collect_files(root: Path) -> Set[str]:
    """Return relative file paths under root."""
    result = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        for fn in filenames:
            rel = str(Path(dirpath).relative_to(root) / fn)
            result.add(rel)
    return result


def collect_definitions(root: Path) -> Dict[str, List[str]]:
    """Return {name: [locations]} for all definitions."""
    import re
    defs: Dict[str, List[str]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        for fn in filenames:
            if not fn.endswith((".py", ".js", ".ts", ".go", ".rs", ".java")):
                continue
            full = Path(dirpath) / fn
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                # Simple function/class name extraction.
                for pat in [r"def\s+(\w+)", r"class\s+(\w+)", r"function\s+(\w+)",
                            r"func\s+(\w+)", r"fn\s+(\w+)"]:
                    for m in __import__("re").finditer(pat, line):
                        name = m.group(1)
                        loc = str(full.relative_to(root))
                        defs.setdefault(name, []).append(loc)
    return defs


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-repo merge conflict preflight")
    parser.add_argument("--repos", nargs="+", required=True, help="repo directories to check")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    repos = [Path(r).resolve() for r in args.repos]
    for r in repos:
        if not r.exists():
            print(f"ERROR: {r} does not exist", file=sys.stderr)
            return 2

    # 1. File path collisions.
    file_sets = {str(r): collect_files(r) for r in repos}
    all_files: Dict[str, List[str]] = {}
    for repo, files in file_sets.items():
        for f in files:
            all_files.setdefault(f, []).append(repo.name)

    collisions = {f: repos_list for f, repos_list in all_files.items()
                  if len(repos_list) > 1}

    # 2. Duplicate definition names.
    def_sets = {str(r): collect_definitions(r) for r in repos}
    all_defs: Dict[str, Dict[str, List[str]]] = {}
    for repo, defs in def_sets.items():
        for name, locs in defs.items():
            all_defs.setdefault(name, {})[repo.name] = locs

    dup_defs = {name: repos for name, repos in all_defs.items()
                if len(repos) > 1}

    report = {
        "repos": [str(r) for r in repos],
        "file_collisions": len(collisions),
        "colliding_files": collisions,
        "duplicate_definitions": len(dup_defs),
        "duplicate_definition_names": list(dup_defs.keys())[:50],
        "clean": len(collisions) == 0 and len(dup_defs) == 0,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Merge preflight: {len(repos)} repos")
        print(f"  File path collisions: {len(collisions)}")
        if collisions:
            for f, rs in list(collisions.items())[:10]:
                print(f"    {f}  <- {rs}")
        print(f"  Duplicate definition names: {len(dup_defs)}")
        if dup_defs:
            for name in list(dup_defs.keys())[:10]:
                print(f"    {name}")
        if report["clean"]:
            print("  RESULT: CLEAN — no collisions detected")
        else:
            print("  RESULT: CONFLICTS FOUND — review before merging")
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
PY