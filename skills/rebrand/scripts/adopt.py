"""Adopt an existing profile into the merged spec tree (SRP: adoption only).

Compares source vs target trees, copies missing files, reports collisions.
Does not overwrite existing target files.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402


def main() -> int:
    """Parse arguments and run adoption."""
    parser = argparse.ArgumentParser(description="Adopt an existing profile into a new tree")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    src, dst = args.source, args.target
    if not src.exists():
        print(f"Source not found: {src}", file=sys.stderr)
        return 2
    dst.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    collisions = []
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        if any(part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"} for part in rel.parts):
            continue
        target_path = dst / rel
        if target_path.exists():
            if target_path.read_bytes() != path.read_bytes():
                collisions.append(str(rel))
            skipped += 1
            continue
        if args.dry_run:
            print(f"  would copy: {rel}")
            copied += 1
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target_path)
        copied += 1

    print(f"Adopt: copied={copied} skipped={skipped} collisions={len(collisions)}")
    if collisions:
        print("Collisions (differing content, not overwritten):")
        for c in collisions[:50]:
            print(f"  {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
