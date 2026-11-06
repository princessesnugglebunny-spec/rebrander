#!/usr/bin/env python3
"""Artifact-level leftover-brand scanner (SRP: artifact verification only).

Source grep cannot see branding compiled into binaries, bundles, minified JS,
APK resources, plists, or manifests. This script scans a built-artifact tree
for old-brand tokens (all case/separator variants) and, when Ablation is
installed, runs `ablation analyze` on each binary for its strings/entropy pass.

REA is detected when present (via `rea` on PATH or npx) but is not invoked
automatically because its exact subcommand depends on the artifact type; the
script reports availability so the agent can drive the matching REA flow from
the `rea` reference checkout.
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
import brand_tokens as bt

SKIP_DIRS = {".git", "node_modules", "__pycache__"}


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return False


def extract_text(path: Path) -> str:
    """Return decodable text (strings for binaries, utf-8 for text)."""
    if is_binary(path):
        if shutil.which("strings"):
            try:
                out = subprocess.run(
                    ["strings", "-a", "-n", "4", str(path)],
                    capture_output=True, text=True, check=False,
                )
                return out.stdout
            except OSError:
                return ""
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def scan_tree(artifacts: Path, variants: List[str]) -> List[Dict]:
    """Scan every file; return list of {file, hits:[{variant,line}]}."""
    results = []
    for dirpath, dirnames, filenames in os.walk(artifacts):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            full = Path(dirpath) / fn
            text = extract_text(full)
            if not text:
                continue
            hits = []
            low_variants = [v.lower() for v in variants]
            for i, line in enumerate(text.splitlines(), 1):
                low = line.lower()
                for v in low_variants:
                    if v in low:
                        hits.append({"variant": v, "line": i, "snippet": line[:120]})
                        break
            if hits:
                results.append({"file": str(full.relative_to(artifacts)), "hits": hits})
    return results


def run_ablation_deep(artifacts: Path) -> List[Dict]:
    """Run `ablation analyze` on each binary when available."""
    if not shutil.which("ablation"):
        return [{"tool": "ablation", "status": "not installed"}]
    out = []
    for dirpath, _dn, filenames in os.walk(artifacts):
        for fn in filenames:
            full = Path(dirpath) / fn
            if not is_binary(full):
                continue
            try:
                r = subprocess.run(
                    ["ablation", "analyze", str(full)],
                    capture_output=True, text=True, check=False, timeout=120,
                )
                out.append({
                    "tool": "ablation",
                    "file": str(full.relative_to(artifacts)),
                    "status": "ok" if r.returncode == 0 else "error",
                    "stdout": r.stdout[:4000],
                    "stderr": r.stderr[:1000],
                })
            except Exception as exc:  # noqa: BLE001
                out.append({"tool": "ablation", "file": str(full.relative_to(artifacts)),
                            "status": "exception", "error": str(exc)})
    if not out:
        out = [{"tool": "ablation", "status": "no binaries found"}]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Artifact-level leftover-brand scanner")
    parser.add_argument("--brand", type=Path, help="path to brand.json (extracts original tokens)")
    parser.add_argument("--token", action="append", default=[], help="old brand token to scan for (repeatable)")
    parser.add_argument("--artifacts", required=True, type=Path, help="built-artifact directory")
    parser.add_argument("--deep", action="store_true", help="also run ablation analyze on binaries")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    tokens: List[str] = list(args.token)
    if args.brand:
        brand = bt.load_brand(args.brand)
        tokens.extend(str(v) for v in brand.get("original", {}).values())

    variants = bt.residual_variants(tokens) if tokens else []
    scan_results = scan_tree(args.artifacts, variants) if variants else []

    deep_results = run_ablation_deep(args.artifacts) if args.deep else []

    rea_available = bool(shutil.which("rea")) or bool(shutil.which("npx"))
    report = {
        "artifacts": str(args.artifacts),
        "tokens_scanned": tokens,
        "variants_scanned": variants,
        "files_with_hits": len(scan_results),
        "scan_results": scan_results,
        "rea_cli_available": rea_available,
        "rea_note": ("REA available; consult the rea reference for the "
                     "artifact-type-specific flow (e.g. analyze-javascript-application)."
                     if rea_available else
                     "REA not installed (npx/rea missing). Offer `npx rea-agents setup`."),
        "deep": deep_results,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"ARTIFACT SCAN — {args.artifacts}")
        print(f"tokens: {tokens}")
        print(f"files with hits: {len(scan_results)}")
        for r in scan_results:
            print(f"  {r['file']}: {len(r['hits'])} hit(s)")
            for h in r["hits"][:5]:
                print(f"      L{h['line']}: {h['snippet']}")
        print(f"REA CLI available: {rea_available}")
        if args.deep:
            print(f"Ablation deep pass: {len(deep_results)} result(s)")
    return 0 if not scan_results else 1


if __name__ == "__main__":
    sys.exit(main())
