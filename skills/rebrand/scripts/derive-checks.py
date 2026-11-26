"""Derive pytest checks from a PLAN.md acceptance list (SRP: derivation only).

Parses '- [ ]' acceptance cases and emits a pytest skeleton pinned to a
hash of the plan. Does not guess at implementation details.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402


def _slug(text: str) -> str:
    """Convert acceptance text to a test function name."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return "test_" + (s[:60] if s else "case")


def main() -> int:
    """Parse arguments and emit derived checks."""
    parser = argparse.ArgumentParser(description="Derive pytest checks from PLAN.md")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    text = args.plan.read_text(encoding="utf-8")
    plan_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    cases = []
    in_acc = False
    for line in text.splitlines():
        if line.strip().lower().startswith("## 8. acceptance") or "acceptance cases" in line.lower():
            in_acc = True
            continue
        if in_acc and line.startswith("## "):
            break
        if in_acc:
            m = re.match(r"\s*-\s*\[\s*[ xX]?\s*\]\s*(.+)", line)
            if m:
                cases.append(m.group(1).strip())

    out_lines = [
        f"# ail-derived-from: plan@{plan_hash}",
        "import pytest",
        "",
    ]
    for case in cases:
        name = _slug(case)
        out_lines.append(f"def {name}():")
        out_lines.append(f'    """{case}"""')
        out_lines.append("    # TODO: implement assertion derived from plan")
        out_lines.append("    pass")
        out_lines.append("")

    args.out.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"Derived {len(cases)} check(s) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
