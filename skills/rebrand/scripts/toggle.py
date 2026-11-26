"""Feature toggle + lockfile regen (SRP: toggling only)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402


def main() -> int:
    """Parse arguments and toggle features."""
    parser = argparse.ArgumentParser(description="Toggle features in brand.json")
    parser.add_argument("--brand", required=True, type=Path)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--regen-lockfile", action="store_true", help="run lockfile regeneration")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    brand = bt.load_brand(args.brand)
    features = brand.setdefault("features", {})
    if args.enable:
        features[args.feature] = True
    elif args.disable:
        features[args.feature] = False
    else:
        print("Specify --enable or --disable", file=sys.stderr)
        return 2
    args.brand.write_text(json.dumps(brand, indent=2), encoding="utf-8")
    print(f"Set feature '{args.feature}' = {features[args.feature]}")

    if args.regen_lockfile and args.root:
        for cmd in (["npm", "install", "--package-lock-only"],):
            try:
                subprocess.run(cmd, cwd=args.root, check=False)
                print(f"Ran: {' '.join(cmd)}")
            except FileNotFoundError:
                print(f"Skipped (not found): {' '.join(cmd)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
