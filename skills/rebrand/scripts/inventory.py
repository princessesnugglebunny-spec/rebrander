#!/usr/bin/env python3
"""Exhaustive function/class/feature inventory extractor (SRP: extraction only).

Scans a source tree and emits a markdown table of named definitions
(functions, classes, types, traits) with kind and location. The agent then
annotates each row with a one-line description and rebrand impact.

Supported (heuristic, regex-based, zero dependencies): Python, JavaScript,
TypeScript, Go, Rust, Java, C#, C, C++. Other languages are skipped and
reported as skipped so the coverage metric stays honest.

Parallel scanning via concurrent.futures for large repos.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "target", "dist", "build", ".next", "vendor"}

# language -> list of (kind, compiled regex with named group 'name')
PATTERNS: Dict[str, List[Tuple[str, re.Pattern]]] = {
    "py": [
        ("function", re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")),
        ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*[\(:]")),
    ],
    "js": [
        ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")),
        ("class", re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)")),
        ("const-fn", re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\(")),
        ("const-fn", re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\b")),
    ],
    "ts": [
        ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*[<(]")),
        ("class", re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)")),
        ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)")),
        ("type", re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=")),
        ("const-fn", re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\(")),
    ],
    "go": [
        ("function", re.compile(r"^func\s+(?:\([^)]*\)\s+)?([A-Za-z_]\w*)\s*\(")),
        ("type", re.compile(r"^type\s+([A-Za-z_]\w*)\s+(?:struct|interface)")),
    ],
    "rs": [
        ("function", re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)\s*[<(]")),
        ("struct", re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_]\w*)")),
        ("enum", re.compile(r"^\s*(?:pub\s+)?enum\s+([A-Za-z_]\w*)")),
        ("trait", re.compile(r"^\s*(?:pub\s+)?trait\s+([A-Za-z_]\w*)")),
        ("impl", re.compile(r"^\s*impl(?:<[^>]*>)?\s+([A-Za-z_]\w*)")),
    ],
    "java": [
        ("class", re.compile(r"^\s*(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?class\s+([A-Za-z_]\w*)")),
        ("interface", re.compile(r"^\s*(?:public\s+)?interface\s+([A-Za-z_]\w*)")),
        ("method", re.compile(r"^\s*(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(?:[\w<>\[\],\s]+)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{")),
    ],
    "cs": [
        ("class", re.compile(r"^\s*(?:public|internal|private|protected)?\s*(?:static\s+|abstract\s+|sealed\s+|partial\s+)*class\s+([A-Za-z_]\w*)")),
        ("interface", re.compile(r"^\s*(?:public|internal)?\s*interface\s+([A-Za-z_]\w*)")),
        ("method", re.compile(r"^\s*(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?(?:[\w<>\[\],\s]+)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{")),
    ],
    "c": [
        ("struct", re.compile(r"^\s*(?:typedef\s+)?struct\s+([A-Za-z_]\w*)\s*\{?")),
        ("function", re.compile(r"^(?:[A-Za-z_][\w\s\*]+)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{")),
    ],
    "cpp": [
        ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)")),
        ("struct", re.compile(r"^\s*struct\s+([A-Za-z_]\w*)")),
        ("function", re.compile(r"^(?:[A-Za-z_][\w\s\*:&<>]+)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*(?:const)?\s*\{")),
    ],
}

EXT_TO_LANG = {
    ".py": "py",
    ".js": "js", ".mjs": "js", ".cjs": "js",
    ".ts": "ts", ".tsx": "ts", ".jsx": "js",
    ".go": "go",
    ".rs": "rs",
    ".java": "java",
    ".cs": "cs",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
}


def detect_lang(path: Path) -> str:
    return EXT_TO_LANG.get(path.suffix.lower(), "")


def scan_file(path: Path, root: Path) -> List[Tuple[str, str, str, str]]:
    """Return list of (name, kind, location, signature)."""
    lang = detect_lang(path)
    if not lang:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return []
    out = []
    rel = str(path.relative_to(root))
    for idx, line in enumerate(lines, 1):
        for kind, pat in PATTERNS.get(lang, []):
            m = pat.search(line)
            if m:
                name = m.group(1)
                sig = line.strip()[:120]
                out.append((name, kind, f"{rel}:{idx}", sig))
    return out


def _collect_files(root: Path) -> List[Path]:
    """Collect candidate source files (parallel-friendly)."""
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            full = Path(dirpath) / fn
            if detect_lang(full):
                result.append(full)
    result.sort()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Function/class inventory extractor")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", type=Path, help="write markdown to file (default stdout)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    parser.add_argument("--workers", type=int, default=4, help="parallel workers (default: 4)")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    root = args.root
    files = _collect_files(root)

    all_defs: List[Tuple[str, str, str, str]] = []
    files_with_defs = 0
    lang_counts: Dict[str, int] = {}
    kind_counts: Dict[str, int] = {}

    # Parallel scan.
    def _scan_one(fpath):
        return fpath, scan_file(fpath, root)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_scan_one, fp): fp for fp in files}
        for fut in as_completed(futures):
            fpath, defs = fut.result()
            if defs:
                files_with_defs += 1
                all_defs.extend(defs)
                for _name, kind, _loc, _sig in defs:
                    kind_counts[kind] = kind_counts.get(kind, 0) + 1
                lang = detect_lang(fpath)
                lang_counts[lang] = lang_counts.get(lang, 0) + len(defs)

    files_scanned = len(files)
    total_files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        total_files += len(filenames)
    files_skipped = total_files - files_scanned

    coverage = (100.0 * files_with_defs / files_scanned) if files_scanned else 0.0

    if args.json:
        report = {
            "root": str(root),
            "files_seen": total_files,
            "files_scanned": files_scanned,
            "files_with_definitions": files_with_defs,
            "files_skipped_unsupported": files_skipped,
            "coverage_percent": round(coverage, 1),
            "definitions_total": len(all_defs),
            "by_language": lang_counts,
            "by_kind": kind_counts,
            "definitions": [
                {"name": n, "kind": k, "location": l, "signature": s}
                for (n, k, l, s) in all_defs
            ],
        }
        text = json.dumps(report, indent=2)
    else:
        lines = []
        lines.append("# Inventory (auto-generated)")
        lines.append("")
        lines.append(f"- Root: `{root}`")
        lines.append(f"- Files seen: {total_files}")
        lines.append(f"- Files scanned (supported langs): {files_scanned}")
        lines.append(f"- Files with definitions: {files_with_defs}")
        lines.append(f"- Files skipped (unsupported ext): {files_skipped}")
        lines.append(f"- Definition coverage: {coverage:.1f}% of scanned files contain >=1 definition")
        lines.append(f"- Total definitions: {len(all_defs)}")
        lines.append(f"- By language: {', '.join(f'{k}={v}' for k, v in sorted(lang_counts.items())) or 'none'}")
        lines.append(f"- By kind: {', '.join(f'{k}={v}' for k, v in sorted(kind_counts.items())) or 'none'}")
        lines.append("")
        lines.append("| Name | Kind | Location | Signature |")
        lines.append("|---|---|---|---|")
        for name, kind, loc, sig in all_defs:
            sig = sig.replace("|", "\\|")
            lines.append(f"| `{name}` | {kind} | `{loc}` | `{sig}` |")
        lines.append("")
        text = "\n".join(lines)

    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {len(all_defs)} definitions to {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY