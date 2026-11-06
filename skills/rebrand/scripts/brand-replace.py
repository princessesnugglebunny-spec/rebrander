#!/usr/bin/env python3
"""Deterministic brand-replacement engine (DRY/SRP/KISS).

Reads brand.json (original + target tokens) and applies mechanical, predictable
replacements across a source tree. Modes:

  --dry-run   report what would change (files, counts, residual hits); no writes
  --diff      print a unified diff of the proposed changes; no writes
  --apply     write changes and report counts

The script never touches binary/undecodable files and never modifies .git or
node_modules. Function and class names touched by the rename stay
self-documenting; every function/class carries a docstring (see values).
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402

DEFAULT_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv",
                     "venv", ".tox", "dist", "build", ".next", "target"}

TEXT_EXTENSIONS = None  # None = accept any decodable file


def is_binary(data: bytes) -> bool:
    """Return True if the bytes look binary (NUL byte in first 8 KiB)."""
    return b"\x00" in data[:8192]


def collect_files(root: Path, skip_dirs: set, excludes: List[str]) -> List[Path]:
    """Walk root and return candidate text files."""
    import fnmatch

    result: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            full = Path(dirpath) / fn
            rel = full.relative_to(root)
            if full.name == "brand.json":
                continue
            if any(fnmatch.fnmatch(str(rel), pat) for pat in excludes):
                continue
            result.append(full)
    result.sort()
    return result


def read_text(path: Path) -> Tuple[str, str]:
    """Return (text, encoding) or raise on binary/undecodable."""
    data = path.read_bytes()
    if is_binary(data):
        raise ValueError("binary")
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        raise ValueError("undecodable")


def apply_replacements(text: str, pairs: List[Tuple[str, str]]) -> Tuple[str, Dict[str, int]]:
    """Apply ordered replacements; return (new_text, per-variant counts)."""
    counts: Dict[str, int] = {}
    result = text
    for old, new in pairs:
        pat = bt.boundary_pattern(old)
        new_text, n = re_sub_count(result, pat, new)
        if n:
            result = new_text
            counts[old] = counts.get(old, 0) + n
    return result, counts


def re_sub_count(text: str, pattern: str, repl: str):
    """re.sub that also returns the replacement count."""
    import re

    compiled = re.compile(pattern)
    count = [0]

    def _repl(m):
        count[0] += 1
        return repl

    new = compiled.sub(_repl, text)
    return new, count[0]


def residual_hits(text: str, tokens: List[str]) -> List[int]:
    """Return 1-based line numbers still containing old tokens (case-insensitive)."""
    low_variants = bt.residual_variants(tokens)
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if any(v in low for v in low_variants):
            hits.append(i)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic brand replacement engine")
    parser.add_argument("--brand", required=True, type=Path, help="path to brand.json")
    parser.add_argument("--root", required=True, type=Path, help="root directory to process")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="report only, no writes")
    mode.add_argument("--diff", action="store_true", help="print unified diff, no writes")
    mode.add_argument("--apply", action="store_true", help="apply replacements")
    parser.add_argument("--out", type=Path, help="write report/diff to file instead of stdout")
    parser.add_argument("--json", action="store_true", help="emit JSON report (dry-run/apply)")
    parser.add_argument("--exclude", action="append", default=[], help="glob to exclude (repeatable)")
    parser.add_argument("--skip-dir", action="append", default=[], help="directory name to skip (repeatable)")
    parser.add_argument("--transactional", action="store_true",
                        help="apply all changes or none: on failure, restore touched files from manifest")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="write list of touched files to this path (default: <root>/brand-replace.manifest.json when --apply)")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    brand = bt.load_brand(args.brand)
    pairs = bt.token_pairs(brand)
    if not pairs:
        print("No token pairs found in brand.json (check 'original'/'target' keys).", file=sys.stderr)
        return 2

    skip_dirs = set(DEFAULT_SKIP_DIRS) | set(args.skip_dir)
    excludes = list(args.exclude)
    files = collect_files(args.root, skip_dirs, excludes)

    # Detect package roots (monorepo awareness).
    package_markers = {"package.json", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle"}
    package_roots = []
    for dirpath, dirnames, filenames in os.walk(args.root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        for fn in filenames:
            if fn in package_markers:
                package_roots.append(str(Path(dirpath).relative_to(args.root) or "."))
    package_roots = sorted(set(package_roots))

    file_reports = []
    total_replacements = 0
    files_changed = 0

    originals: dict = {}
    original_tokens = list(brand.get("original", {}).values())

    touched_files: List[str] = []

    for path in files:
        try:
            text, _enc = read_text(path)
        except ValueError:
            continue

        new_text, counts = apply_replacements(text, pairs)
        n = sum(counts.values())
        if n == 0 and new_text == text:
            # Still check residuals for dry-run.
            res = residual_hits(text, original_tokens)
            if args.dry_run and res:
                file_reports.append({
                    "file": str(path.relative_to(args.root)),
                    "replacements": 0,
                    "residual_lines": res,
                })
            continue

        rel = str(path.relative_to(args.root))
        files_changed += 1
        total_replacements += n

        if args.diff:
            diff = difflib.unified_diff(
                text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
            out_text = "".join(diff)
            if args.out:
                with args.out.open("a", encoding="utf-8") as fh:
                    fh.write(out_text)
            else:
                sys.stdout.write(out_text)
            continue

        if args.apply:
            try:
                tmp = path.with_suffix(path.suffix + ".brandtmp")
                tmp.write_text(new_text, encoding="utf-8")
                os.replace(tmp, path)
                touched_files.append(rel)
                if args.transactional:
                    originals[rel] = text
            except OSError as exc:
                print(f"ERROR writing {rel}: {exc}", file=sys.stderr)
                if args.transactional:
                    # Rollback all touched files.
                    print("Transactional mode: rolling back...", file=sys.stderr)
                    for tf in touched_files:
                        tp = args.root / tf
                        if tf in originals:
                            tp.write_text(originals[tf], encoding="utf-8")
                    # Clean up temp files.
                    for tf in touched_files:
                        tmp = (args.root / tf).with_suffix(
                            (args.root / tf).suffix + ".brandtmp")
                        if tmp.exists():
                            tmp.unlink()
                    print(f"Rolled back {len(touched_files)} file(s).", file=sys.stderr)
                return 1

        res = residual_hits(new_text, original_tokens)
        file_reports.append({
            "file": rel,
            "replacements": n,
            "by_variant": counts,
            "residual_lines": res,
        })

    # Dry-run summary reporting.
    if args.dry_run:
        if args.json:
            report = {
                "root": str(args.root),
                "packages_detected": package_roots,
                "files_scanned": len(files),
                "files_changed": files_changed,
                "total_replacements": total_replacements,
                "files": file_reports,
            }
            print(json.dumps(report, indent=2))
        else:
            print(f"DRY RUN — root: {args.root}")
            if package_roots:
                print(f"packages detected: {package_roots}")
            print(f"files scanned: {len(files)}  files that would change: {files_changed}  "
                  f"total replacements: {total_replacements}")
            print("-" * 70)
            for fr in file_reports:
                if fr["replacements"]:
                    print(f"{fr['replacements']:5d}\t{fr['file']}")
            # Residuals.
            any_res = False
            for fr in file_reports:
                if fr.get("residual_lines"):
                    if not any_res:
                        print("-" * 70)
                        print("RESIDUAL (manual review needed):")
                        any_res = True
                    print(f"  {fr['file']}: lines {fr['residual_lines']}")
            if not any_res and files_changed == 0:
                print("No replacements would be made and no residual hits found.")
        return 0

    if args.apply:
        if args.json:
            report = {
                "root": str(args.root),
                "packages_detected": package_roots,
                "files_changed": files_changed,
                "total_replacements": total_replacements,
                "files": file_reports,
            }
            print(json.dumps(report, indent=2))
        else:
            print(f"APPLIED — files changed: {files_changed}  total replacements: {total_replacements}")
            for fr in file_reports:
                if fr["residual_lines"]:
                    print(f"  RESIDUAL {fr['file']}: lines {fr['residual_lines']}")
        # Write manifest of touched files (always, in apply mode).
        manifest_path = args.manifest or (args.root / "brand-replace.manifest.json")
        manifest_path.write_text(
            json.dumps({"touched": [fr["file"] for fr in file_reports]}, indent=2),
            encoding="utf-8",
        )
        if not args.json:
            print(f"  Manifest written to {manifest_path}")
        return 0

    # --diff with --out handled inline; if no --out, already streamed.
    if args.diff and not args.out:
        return 0
    if args.diff and args.out:
        print(f"Diff written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
