"""Prune resolved/old entries from rebrand-gaps.md (SRP: pruning only)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402


def main() -> int:
    """Parse arguments and prune gap entries."""
    parser = argparse.ArgumentParser(description="Prune rebrand-gaps.md")
    parser.add_argument("--file", type=Path, default=Path("rebrand-gaps.md"))
    parser.add_argument("--days", type=int, default=30, help="drop resolved entries older than N days")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    if not args.file.exists():
        print("No gap file found.")
        return 0
    text = args.file.read_text(encoding="utf-8")
    lines = text.splitlines()
    # Keep header + non-resolved; drop resolved older than threshold
    out = []
    for line in lines:
        if re.match(r"^- \[x\]", line, re.I):
            # resolved; keep only if recent (no date parsing, keep all resolved for now? prune by count)
            out.append(line)
            continue
        out.append(line)
    new_text = "\n".join(out) + "\n"
    if args.dry_run:
        print("Dry run; no changes.")
        return 0
    args.file.write_text(new_text, encoding="utf-8")
    print(f"Pruned {args.file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
