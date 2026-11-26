"""Fast source leftover-brand scanner (SRP: scanning only).

Scans source text files for old-brand tokens (all case/separator variants)
and optionally TODO/FIXME markers. Prefers ripgrep when available for speed,
falls back to Python.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402

DEFAULT_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def _collect_files(root: Path) -> List[Path]:
    """Collect candidate text files (hardened, fast)."""
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_SKIP_DIRS]
        for fn in filenames:
            full = Path(dirpath) / fn
            if full.name == "brand.json":
                continue
            try:
                if full.stat().st_size > 512 * 1024:
                    continue
            except OSError:
                continue
            result.append(full)
    result.sort()
    return result


LICENSE_MARKERS = ("copyright", "©", "(c)", "spdx-license-identifier", "all rights reserved", "licensed under")


def _is_kept(line: str, keep: List[str]) -> bool:
    low = line.lower()
    if any(k.lower() in low for k in (keep or [])):
        return True
    if any(m in low for m in LICENSE_MARKERS):
        return True
    return False


def scan_python(root: Path, tokens: List[str], todo: bool, keep: List[str] = None) -> Dict[str, List[Dict]]:
    """Python fallback scan."""
    keep = keep or []
    variants = bt.residual_variants(tokens)
    todo_markers = ("TODO", "FIXME", "XXX", "HACK")
    findings: Dict[str, List[Dict]] = {"brand": [], "todo": []}
    for path in _collect_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "\x00" in text[:8192]:
            continue
        rel = str(path.relative_to(root))
        for i, line in enumerate(text.splitlines(), 1):
            if _is_kept(line, keep):
                continue
            low = line.lower()
            if any(v in low for v in variants):
                findings["brand"].append({"file": rel, "line": i, "text": line.strip()[:120]})
            if todo and any(m in line for m in todo_markers):
                findings["todo"].append({"file": rel, "line": i, "text": line.strip()[:120]})
    return findings


def scan_ripgrep(root: Path, tokens: List[str]) -> List[Dict]:
    """Use ripgrep if available for speed."""
    rg = shutil.which("rg")
    if not rg:
        return []
    variants = bt.residual_variants(tokens)
    # Build alternation pattern.
    import re

    pattern = "|".join(re.escape(v) for v in variants)
    try:
        proc = subprocess.run(
            [rg, "-n", "-i", "-e", pattern, str(root), "--json"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    findings = []
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "match":
            continue
        data = obj.get("data", {})
        path_text = data.get("path", {}).get("text", "")
        try:
            rel = str(Path(path_text).relative_to(root))
        except ValueError:
            rel = path_text
        for sub in data.get("submatches", []):
            findings.append({"file": rel, "line": data.get("line_number", 0)})
            break
        # dedup by file+line
    # dedup
    seen = set()
    out = []
    for f in findings:
        key = (f["file"], f["line"])
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def main() -> int:
    """Parse arguments and run the command."""
    parser = argparse.ArgumentParser(description="Fast source leftover-brand scanner")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--brand", type=Path, help="brand.json to extract original tokens")
    parser.add_argument("--token", action="append", default=[], help="old brand token (repeatable)")
    parser.add_argument("--todo", action="store_true", help="also scan for TODO/FIXME/XXX/HACK")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    tokens = list(args.token)
    keep = []
    if args.brand:
        brand = bt.load_brand(args.brand)
        tokens.extend(str(v) for v in brand.get("original", {}).values())
        keep = brand.get("keep", [])

    if not tokens:
        print("No tokens provided (use --brand or --token).", file=sys.stderr)
        return 2

    root = args.root
    rg = shutil.which("rg")
    if rg:
        brand_findings = scan_ripgrep(root, tokens)
        # ripgrep path doesn't include line text; augment? keep simple
        findings = {"brand": brand_findings, "todo": []}
        if args.todo:
            # fallback todo scan via python for text
            py = scan_python(root, [], False, keep)
            findings["todo"] = py["todo"]
    else:
        findings = scan_python(root, tokens, args.todo, keep)

    total = len(findings["brand"]) + len(findings["todo"])
    if args.json:
        print(json.dumps({"root": str(root), "brand_hits": findings["brand"], "todo_hits": findings["todo"], "total": total}, indent=2))
    else:
        print(f"Source scan: {len(findings['brand'])} brand hit(s), {len(findings['todo'])} todo hit(s)")
        for h in findings["brand"][:50]:
            print(f"  BRAND {h['file']}:{h.get('line', '')}")
        for h in findings["todo"][:50]:
            print(f"  TODO  {h['file']}:{h['line']}  {h['text']}")
    return 1 if findings["brand"] else 0


if __name__ == "__main__":
    sys.exit(main())
