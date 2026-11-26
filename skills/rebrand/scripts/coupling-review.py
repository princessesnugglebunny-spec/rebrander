"""Coupling/modernization review (SRP: review only)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402

PATTERNS = {
    "hardcoded-url": re.compile(r"https?://[a-zA-Z0-9.\-]+", re.I),
    "tenant-id": re.compile(r"tenant[_-]?id|org[_-]?id|account[_-]?id", re.I),
    "auth-provider": re.compile(r"auth0|okta|azuread|cognito|firebase", re.I),
    "env-assumption": re.compile(r"os\.environ|process\.env\.[A-Z_]+", re.I),
    "org-specific": re.compile(r"internal\.|corp\.|intranet\.", re.I),
}


def main() -> int:
    """Parse arguments and run the review."""
    parser = argparse.ArgumentParser(description="Coupling/modernization review")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    findings = {k: [] for k in PATTERNS}
    for dirpath, dirnames, filenames in os.walk(args.root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        for fn in filenames:
            full = Path(dirpath) / fn
            try:
                if full.stat().st_size > 512 * 1024:
                    continue
                text = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "\x00" in text[:8192]:
                continue
            rel = str(full.relative_to(args.root))
            for i, line in enumerate(text.splitlines(), 1):
                for name, pat in PATTERNS.items():
                    if pat.search(line):
                        findings[name].append({"file": rel, "line": i, "text": line.strip()[:100]})
                        break

    total = sum(len(v) for v in findings.values())
    if args.json:
        print(json.dumps({"root": str(args.root), "findings": findings, "total": total}, indent=2))
    else:
        print(f"Coupling review: {total} finding(s)")
        for name, items in findings.items():
            if items:
                print(f"  {name}: {len(items)}")
                for it in items[:10]:
                    print(f"    {it['file']}:{it['line']}")
    if args.out:
        lines = ["# Modernization track", "", f"Total findings: {total}", ""]
        for name, items in findings.items():
            if items:
                lines.append(f"## {name} ({len(items)})")
                for it in items[:50]:
                    lines.append(f"- {it['file']}:{it['line']} — {it['text']}")
                lines.append("")
        args.out.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
