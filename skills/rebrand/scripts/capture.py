"""Capture observable behavior of a target (SRP: capture only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402


def _hash_file(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return ""


def main() -> int:
    """Parse arguments and capture."""
    parser = argparse.ArgumentParser(description="Capture observable behavior")
    parser.add_argument("--scenario", required=True, help="scenario name")
    parser.add_argument("--command", required=True, help="command to run (shell)")
    parser.add_argument("--root", required=True, type=Path, help="target root")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    try:
        r = subprocess.run(args.command, shell=True, cwd=args.root, capture_output=True, text=True, timeout=300)
        rc = r.returncode
        stdout = r.stdout
        stderr = r.stderr
    except Exception as exc:
        rc = -1
        stdout = ""
        stderr = str(exc)

    capture = {
        "scenario": args.scenario,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "command": args.command,
        "exit_code": rc,
        "stdout": stdout[:4000],
        "stderr": stderr[:2000],
        "file_hashes": {str(p.relative_to(args.root)): _hash_file(p) for p in args.root.rglob("*") if p.is_file()} if args.root.exists() else {},
    }
    args.out.write_text(json.dumps(capture, indent=2), encoding="utf-8")
    print(f"Capture written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
