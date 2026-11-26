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
try:
    import cache as _cache  # noqa: E402
except Exception:
    _cache = None

DEFAULT_SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    "dist",
    "build",
    ".next",
    "target",
}


def is_binary(data: bytes) -> bool:
    """Return True if the bytes look binary (NUL byte in first 8 KiB)."""
    return b"\x00" in data[:8192]


def collect_files(root: Path, skip_dirs: set, excludes: List[str], max_file_size: int = 512 * 1024) -> List[Path]:
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
            try:
                if full.stat().st_size > max_file_size:
                    continue
            except OSError:
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
        """Return the replacement text and increment the count."""
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


class WriteFailure(Exception):
    """Raised when a replacement cannot be written."""

    def __init__(self, relative: str, cause: OSError) -> None:
        """Store the relative path and the underlying OS error."""
        super().__init__(str(cause))
        self.relative = relative
        self.cause = cause


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Deterministic brand replacement engine")
    parser.add_argument("--brand", required=True, type=Path, help="path to brand.json")
    parser.add_argument("--root", required=True, type=Path, help="root directory to process")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="report only, no writes")
    mode.add_argument("--diff", action="store_true", help="print unified diff, no writes")
    mode.add_argument("--apply", action="store_true", help="apply replacements")
    parser.add_argument("--out", type=Path, help="write report/diff to file instead of stdout")
    parser.add_argument("--json", action="store_true", help="emit JSON report (dry-run/apply)")
    parser.add_argument(
        "--exclude", action="append", default=[], help="glob to exclude (repeatable)"
    )
    parser.add_argument(
        "--skip-dir", action="append", default=[], help="directory name to skip (repeatable)"
    )
    parser.add_argument(
        "--config", type=Path, default=None, help="path to .rebranderrc or rebrander.config.json"
    )
    parser.add_argument(
        "--progress", action="store_true", help="show progress (file count) during scan"
    )
    parser.add_argument("--workers", type=int, default=4, help="parallel workers (default: 4)")
    parser.add_argument("--incremental", action="store_true", help="skip files whose content hash matches cache")
    parser.add_argument("--cache-file", type=Path, default=None, help="path to incremental cache JSON")
    parser.add_argument("--max-file-size", type=int, default=512 * 1024, help="skip files larger than this (bytes)")
    parser.add_argument("--idempotent-check", action="store_true", help="apply then verify second run has 0 changes")
    parser.add_argument(
        "--transactional",
        action="store_true",
        help="apply all changes or none: on failure, restore touched files from manifest",
    )
    parser.add_argument(
        "--diff-out", type=Path, default=None, help="write unified diff to this file (with --diff)"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="write list of touched files to this path (default: <root>/brand-replace.manifest.json when --apply)",
    )
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    return parser


def configure(args: argparse.Namespace) -> None:
    """Apply .rebranderrc defaults for skip directories and excludes."""
    config = bt.load_config(args.config or args.root)
    if not args.skip_dir and config.get("skip_dirs"):
        args.skip_dir = config["skip_dirs"]
    if not args.exclude and config.get("excludes"):
        args.exclude = config["excludes"]


def detect_package_roots(root: Path) -> List[str]:
    """Return relative package roots detected under root."""
    package_markers = {
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
    }
    package_roots = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        for filename in filenames:
            if filename in package_markers:
                package_roots.append(str(Path(dirpath).relative_to(root) or "."))
    return sorted(set(package_roots))


def write_diff(args: argparse.Namespace, relative: str, text: str, new_text: str) -> None:
    """Write a unified diff to the configured destination."""
    diff = difflib.unified_diff(
        text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{relative}",
        tofile=f"b/{relative}",
    )
    out_text = "".join(diff)
    destination = args.diff_out or args.out
    if destination:
        with destination.open("a", encoding="utf-8") as handle:
            handle.write(out_text)
    else:
        sys.stdout.write(out_text)


def rollback(root: Path, touched_files: List[str], originals: dict) -> None:
    """Restore touched files and remove temporary files after a write failure."""
    print("Transactional mode: rolling back...", file=sys.stderr)
    for relative in touched_files:
        target = root / relative
        if relative in originals:
            target.write_text(originals[relative], encoding="utf-8")
    for relative in touched_files:
        temporary = (root / relative).with_suffix((root / relative).suffix + ".brandtmp")
        if temporary.exists():
            temporary.unlink()
    print(f"Rolled back {len(touched_files)} file(s).", file=sys.stderr)


def process_file(
    path: Path,
    args: argparse.Namespace,
    root: Path,
    pairs: List[Tuple[str, str]],
    original_tokens: List[str],
) -> dict | None:
    """Process one file and return its report, or None when nothing changed."""
    try:
        text, _encoding = read_text(path)
    except ValueError:
        return None

    new_text, counts = apply_replacements(text, pairs)
    replacements = sum(counts.values())
    if replacements == 0 and new_text == text:
        if args.dry_run:
            residual = residual_hits(text, original_tokens)
            if residual:
                return {
                    "file": str(path.relative_to(root)),
                    "replacements": 0,
                    "residual_lines": residual,
                }
        return None

    relative = str(path.relative_to(root))
    if args.diff:
        write_diff(args, relative, text, new_text)
        return {
            "file": relative,
            "replacements": replacements,
            "changed": True,
            "diff_only": True,
        }

    if args.apply:
        try:
            temporary = path.with_suffix(path.suffix + ".brandtmp")
            temporary.write_text(new_text, encoding="utf-8")
            os.replace(temporary, path)
        except OSError as exc:
            raise WriteFailure(relative, exc) from exc

    report = {
        "file": relative,
        "replacements": replacements,
        "by_variant": counts,
        "residual_lines": residual_hits(new_text, original_tokens),
        "changed": True,
    }
    if args.apply:
        report["touched"] = True
        if args.transactional:
            report["original"] = text
    return report


def emit_dry_run(
    args: argparse.Namespace,
    root: Path,
    files: List[Path],
    package_roots: List[str],
    file_reports: List[dict],
    files_changed: int,
    total_replacements: int,
) -> None:
    """Print the dry-run report as JSON or text."""
    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "packages_detected": package_roots,
                    "files_scanned": len(files),
                    "files_changed": files_changed,
                    "total_replacements": total_replacements,
                    "files": file_reports,
                },
                indent=2,
            )
        )
        return

    print(f"DRY RUN — root: {root}")
    if package_roots:
        print(f"packages detected: {package_roots}")
    print(
        f"files scanned: {len(files)}  files that would change: {files_changed}  "
        f"total replacements: {total_replacements}"
    )
    print("-" * 70)
    for report in file_reports:
        if report["replacements"]:
            print(f"{report['replacements']:5d}	{report['file']}")
    any_residual = False
    for report in file_reports:
        if report.get("residual_lines"):
            if not any_residual:
                print("-" * 70)
                print("RESIDUAL (manual review needed):")
                any_residual = True
            print(f"  {report['file']}: lines {report['residual_lines']}")
    if not any_residual and files_changed == 0:
        print("No replacements would be made and no residual hits found.")


def emit_apply(
    args: argparse.Namespace,
    root: Path,
    package_roots: List[str],
    file_reports: List[dict],
    files_changed: int,
    total_replacements: int,
) -> None:
    """Print the apply report, then write the manifest of touched files."""
    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "packages_detected": package_roots,
                    "files_changed": files_changed,
                    "total_replacements": total_replacements,
                    "files": file_reports,
                },
                indent=2,
            )
        )
    else:
        print(f"APPLIED — files changed: {files_changed}  total replacements: {total_replacements}")
        for report in file_reports:
            if report["residual_lines"]:
                print(f"  RESIDUAL {report['file']}: lines {report['residual_lines']}")

    manifest_path = args.manifest or (root / "brand-replace.manifest.json")
    manifest_path.write_text(
        json.dumps({"touched": [report["file"] for report in file_reports]}, indent=2),
        encoding="utf-8",
    )
    if not args.json:
        print(f"  Manifest written to {manifest_path}")



def _prepare_work_files(args, files, root):
    """Apply incremental cache filtering; return (work_files, cache_file, cache_data, ch)."""
    import hashlib

    def _ch(path):
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return ""

    cache_file = args.cache_file or (root / ".rebrand-cache.json")
    cache_data = {}
    if args.incremental and cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache_data = {}
    work_files = files
    if args.incremental:
        filtered = []
        for path in files:
            rel = str(path.relative_to(root))
            h = _ch(path)
            cached = cache_data.get(rel)
            if cached and cached.get("hash") == h:
                continue
            filtered.append(path)
        work_files = filtered
    return work_files, cache_file, cache_data, _ch



def _do_compute(args, files, pairs, original_tokens, root):
    """Parallel read/compute for dry-run/diff; returns tuple or None on failure."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import hashlib

    def _ch(path):
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return ""

    cache_file = args.cache_file or (root / ".rebrand-cache.json")
    cache_data = {}
    if getattr(args, "incremental", False) and cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache_data = {}
    work_files = files
    if getattr(args, "incremental", False):
        filtered = []
        for path in files:
            rel = str(path.relative_to(root))
            h = _ch(path)
            cached = cache_data.get(rel)
            if cached and cached.get("hash") == h:
                continue
            filtered.append(path)
        work_files = filtered

    def _compute(path):
        try:
            report = process_file(path, args, root, pairs, original_tokens)
            return path, report, None
        except WriteFailure as failure:
            return path, None, failure

    done = 0
    total_work = len(work_files)
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, getattr(args, "workers", 4))) as pool:
        futures = {pool.submit(_compute, fp): fp for fp in work_files}
        for fut in as_completed(futures):
            path, report, failure = fut.result()
            done += 1
            if getattr(args, "progress", False) and (done % 100 == 0 or done == total_work):
                print(f"  processed {done}/{total_work}", file=sys.stderr, flush=True)
            if failure is not None:
                print(f"ERROR writing {failure.relative}: {failure.cause}", file=sys.stderr)
                return None
            results[path] = report
    file_reports = []
    files_changed = 0
    total_replacements = 0
    for path in sorted(work_files):
        report = results.get(path)
        if report is None:
            continue
        if report.get("changed"):
            files_changed += 1
            total_replacements += report["replacements"]
        if report.get("diff_only"):
            continue
        file_reports.append(report)
    return file_reports, files_changed, total_replacements



def _run_idempotent_check(args):
    """Run a second dry-run and return True if clean (0 changes)."""
    args2 = argparse.Namespace(**{k: v for k, v in vars(args).items() if not k.startswith("_")})
    args2.apply = False
    args2.dry_run = True
    args2.diff = False
    files2 = collect_files(args2.root, set(DEFAULT_SKIP_DIRS) | set(args2.skip_dir), list(args2.exclude), args2.max_file_size)
    pairs2 = bt.token_pairs(bt.load_brand(args2.brand))
    original_tokens2 = list(bt.load_brand(args2.brand).get("original", {}).values())
    res = _do_compute(args2, files2, pairs2, original_tokens2, args2.root)
    if res is None:
        return False
    fr2, fc2, tr2 = res
    print(f"Idempotency: second run files_changed={fc2} replacements={tr2}")
    return fc2 == 0 and tr2 == 0



def _do_apply(args, files, pairs, original_tokens, root):
    """Sequential apply path; returns tuple or None on failure."""
    file_reports = []
    files_changed = 0
    total_replacements = 0
    touched_files = []
    originals = {}
    cache_file = args.cache_file or (root / ".rebrand-cache.json")
    cache_data = {}
    if getattr(args, "incremental", False) and cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache_data = {}

    def _ch(path):
        import hashlib

        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return ""

    work_files = files
    if getattr(args, "incremental", False):
        filtered = []
        for path in files:
            rel = str(path.relative_to(root))
            h = _ch(path)
            cached = cache_data.get(rel)
            if cached and cached.get("hash") == h:
                continue
            filtered.append(path)
        work_files = filtered
    for done, path in enumerate(work_files, 1):
        if getattr(args, "progress", False) and (done % 100 == 0 or done == len(work_files)):
            print(f"  processed {done}/{len(work_files)}", file=sys.stderr, flush=True)
        try:
            report = process_file(path, args, root, pairs, original_tokens)
        except WriteFailure as failure:
            print(f"ERROR writing {failure.relative}: {failure.cause}", file=sys.stderr)
            if getattr(args, "transactional", False):
                rollback(root, touched_files, originals)
            return None
        if report is None:
            continue
        if report.get("changed"):
            files_changed += 1
            total_replacements += report["replacements"]
        if report.get("diff_only"):
            continue
        if report.get("touched"):
            touched_files.append(report["file"])
            if getattr(args, "transactional", False):
                originals[report["file"]] = report.pop("original")
        file_reports.append(report)
        if getattr(args, "incremental", False):
            rel = str(path.relative_to(root))
            cache_data[rel] = {"hash": _ch(path)}
    if getattr(args, "incremental", False) and getattr(args, "apply", False):
        try:
            cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        except OSError:
            pass
    return file_reports, files_changed, total_replacements, touched_files, originals


def main() -> int:
    """Parse arguments, run the selected mode, and return the exit code."""
    args = build_parser().parse_args()
    brand = bt.load_brand(args.brand)
    configure(args)
    if args.idempotent_check:
        # First apply.
        args.apply = True
        args.dry_run = False
        args.diff = False
        # Re-parse not needed; run apply via recursive main? Instead just proceed with apply then check.
        # We'll set a flag to run a second dry-run after apply completes.
        args._idempotent = True
    else:
        args._idempotent = False
    pairs = bt.token_pairs(brand)
    if not pairs:
        print(
            "No token pairs found in brand.json (check 'original'/'target' keys).", file=sys.stderr
        )
        return 2

    skip_dirs = set(DEFAULT_SKIP_DIRS) | set(args.skip_dir)
    excludes = list(args.exclude)
    files = collect_files(args.root, skip_dirs, excludes, args.max_file_size)
    package_roots = detect_package_roots(args.root)
    original_tokens = list(brand.get("original", {}).values())

    file_reports: List[dict] = []
    total_replacements = 0
    files_changed = 0
    touched_files: List[str] = []
    originals: dict = {}

    if args.apply:
        out = _do_apply(args, files, pairs, original_tokens, args.root)
        if out is None:
            return 1
        file_reports, files_changed, total_replacements, touched_files, originals = out
    else:
        res = _do_compute(args, files, pairs, original_tokens, args.root)
        if res is None:
            return 1
        file_reports, files_changed, total_replacements = res

    if args.dry_run:
        emit_dry_run(
            args,
            args.root,
            files,
            package_roots,
            file_reports,
            files_changed,
            total_replacements,
        )
        return 0

    if args.apply:
        emit_apply(
            args,
            args.root,
            package_roots,
            file_reports,
            files_changed,
            total_replacements,
        )
        # Write receipt if no residual leftovers.
        residual_count = sum(1 for r in file_reports if r.get("residual_lines"))
        if residual_count == 0:
            receipt = args.root / "brand-replace.receipt.json"
            try:
                receipt.write_text(json.dumps({"status": "verified", "files_changed": files_changed, "total_replacements": total_replacements}, indent=2), encoding="utf-8")
                print(f"  Receipt written to {receipt}")
            except OSError:
                pass
        if getattr(args, "_idempotent", False):
            if not _run_idempotent_check(args):
                return 1
        return 0

    if args.diff and args.out:
        print(f"Diff written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
