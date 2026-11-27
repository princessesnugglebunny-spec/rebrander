"""Review SKILL.md against context-engineering budgets (SRP: review only)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402


def main() -> int:
    """Parse arguments and review."""
    parser = argparse.ArgumentParser(description="Review SKILL.md budgets")
    parser.add_argument("--skill", type=Path, default=Path("SKILL.md"))
    parser.add_argument("--max-body", type=int, default=80)
    parser.add_argument("--max-desc", type=int, default=1024)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    text = args.skill.read_text(encoding="utf-8")
    # frontmatter
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    desc = ""
    if m:
        for line in m.group(1).splitlines():
            if line.startswith("description:"):
                desc = line[len("description:"):].strip()
    # body after second ---
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text
    body_lc = len(body.splitlines())

    issues = []
    if body_lc > args.max_body:
        issues.append(f"body {body_lc} lines > {args.max_body}")
    if len(desc) > args.max_desc:
        issues.append(f"description {len(desc)} chars > {args.max_desc}")
    if not desc:
        issues.append("missing description")
    # frontmatter checks
    if "name:" not in (m.group(1) if m else ""):
        issues.append("missing name in frontmatter")
    if "triggers" not in text.lower() and "trigger" not in text.lower():
        issues.append("no trigger phrases mentioned")

    result = {"body_lines": body_lc, "desc_chars": len(desc), "issues": issues, "pass": not issues}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"SKILL review: {'PASS' if not issues else 'FAIL'}")
        for i in issues:
            print(f"  - {i}")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
