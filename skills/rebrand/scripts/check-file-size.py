#!/usr/bin/env python3
"""Enforce the 666-line file-size ceiling across the repository."""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402

import argparse
import json
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
}
SKIP_SUFFIXES = {
    ".gif",
    ".gz",
    ".ico",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".tar",
    ".ttf",
    ".whl",
    ".woff",
    ".woff2",
    ".zip",
}


def count_lines(path: Path) -> int:
    """Return the line count for a UTF-8 text file, or -1 when unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return -1
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def find_violations(root: Path, limit: int) -> list[dict]:
    """Walk root and return files whose line count exceeds the limit."""
    violations = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        lines = count_lines(path)
        if lines > limit:
            violations.append({"file": str(relative), "lines": lines})
    return violations


def main() -> int:
    """Parse arguments, scan the tree, and return a failing status on violations."""
    parser = argparse.ArgumentParser(description="Enforce the 666-line file-size ceiling")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--limit", type=int, default=666)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    violations = find_violations(args.root, args.limit)
    if args.json:
        print(json.dumps({"limit": args.limit, "violations": violations}, indent=2))
    else:
        for violation in violations:
            print(f"{violation['file']}: {violation['lines']} lines (limit {args.limit})")
        if not violations:
            print(f"File-size check passed (limit {args.limit}).")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
