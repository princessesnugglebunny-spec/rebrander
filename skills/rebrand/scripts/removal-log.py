#!/usr/bin/env python3
"""Removal log (P1): audit trail of attribution/license files removed.

Records which files and header blocks were removed during a rebrand, with
timestamps and reasons, so the new "remove attribution" rule leaves an
auditable trail (supports compliance review of the rebrand).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ATTRIBUTION_NAMES = {
    "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENSE.rst",
    "COPYRIGHT", "COPYRIGHT.md", "COPYRIGHT.txt",
    "NOTICE", "NOTICE.md", "NOTICE.txt",
    "THIRD_PARTY_NOTICES.md", "THIRD-PARTY-NOTICES", "THIRD_PARTY_NOTICES.txt",
    "AUTHORS", "AUTHORS.md", "CONTRIBUTORS", "CONTRIBUTORS.md",
}

HEADER_MARKERS = (
    "copyright", "licensed under", "license", "all rights reserved",
    "spdx-license-identifier", "author:", "contributors:",
)


def detect_removed_files(root: Path) -> List[Dict]:
    """Heuristic: list attribution files that are ABSENT (already removed).

    Used when the log is generated after the fact. For pre-removal planning,
    pass --plan with a list of paths.
    """
    # We can't know what was removed without git; instead, scan for any that
    # remain and report them as "not yet removed".
    remaining = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        for fn in filenames:
            if fn in ATTRIBUTION_NAMES or fn.upper().startswith("LICENSE"):
                remaining.append(str(Path(dirpath).relative_to(root) / fn))
    return remaining


def scan_header_blocks(root: Path) -> List[Dict]:
    """Find source files whose top comments still contain attribution markers."""
    hits = []
    code_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".go",
                 ".rs", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift",
                 ".kt", ".scala"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        for fn in filenames:
            if Path(fn).suffix.lower() not in code_exts:
                continue
            full = Path(dirpath) / fn
            try:
                lines = full.read_text(encoding="utf-8", errors="replace").splitlines()[:15]
            except OSError:
                continue
            block = "\n".join(lines).lower()
            markers = [m for m in HEADER_MARKERS if m in block]
            if markers:
                hits.append({
                    "file": str(full.relative_to(root)),
                    "markers": markers,
                })
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Attribution removal audit log")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--removed", nargs="*", default=[],
                        help="paths that were removed (space-separated)")
    parser.add_argument("--reason", default="rebrand: attribution stripped per rebrand policy",
                        help="reason recorded for each removal")
    parser.add_argument("--out", type=Path, help="output log path (default: removal-log.json in root)")
    parser.add_argument("--scan", action="store_true",
                        help="scan for remaining attribution files/headers instead of logging removals")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    if args.scan:
        remaining_files = detect_removed_files(args.root)
        header_hits = scan_header_blocks(args.root)
        report = {
            "mode": "scan",
            "root": str(args.root),
            "remaining_attribution_files": remaining_files,
            "files_with_attribution_headers": header_hits,
            "clean": not remaining_files and not header_hits,
        }
        print(json.dumps(report, indent=2))
        return 0 if report["clean"] else 1

    out_path = args.out or (args.root / "removal-log.json")
    entries = []
    for p in args.removed:
        entries.append({
            "path": p,
            "type": "file",
            "reason": args.reason,
            "removed_at": datetime.now(timezone.utc).isoformat(),
        })

    # If a log already exists, append.
    existing = []
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text()).get("removals", [])
        except json.JSONDecodeError:
            existing = []
    existing.extend(entries)

    log = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(args.root),
        "policy": "original LICENSE/COPYRIGHT/NOTICE/attribution removed during rebrand; "
                  "replacement license files created only if requested",
        "removals": existing,
    }
    out_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"Removal log written to {out_path} ({len(entries)} new entries, "
          f"{len(existing)} total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
