"""Capture a pre-rebrand baseline snapshot (SRP: snapshot only)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent


def _count_files(root: Path) -> int:
    """Count files under root."""
    n = 0
    for p in root.rglob("*"):
        if p.is_file():
            n += 1
    return n


def main() -> int:
    """Parse arguments and write baseline.json."""
    parser = argparse.ArgumentParser(description="Capture pre-rebrand baseline")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()
    root = args.root
    out = args.out or (root.parent / "baseline.json")
    # inventory count via subprocess
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "inventory.py"), "--root", str(root), "--json"],
        capture_output=True,
        text=True,
    )
    inv = {}
    try:
        inv = json.loads(proc.stdout)
    except json.JSONDecodeError:
        inv = {}
    baseline = {
        "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "root": str(root),
        "file_count": _count_files(root),
        "definitions": inv.get("definitions_total", 0),
        "files_scanned": inv.get("files_scanned", 0),
    }
    out.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    print(f"Baseline written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
