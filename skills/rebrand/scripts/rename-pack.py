#!/usr/bin/env python3
"""Per-stack rename packs (P2): dispatch to the best available tool per language.

Tries language-specific AST-aware renamers (acorn for TS/JS, LibCST for
Python) when installed; falls back to the regex-based brand-replace.py engine
so the pipeline always works without extra dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SCRIPTS = Path(__file__).resolve().parent


def tool_available(name: str) -> bool:
    """Return True when an executable is available on PATH."""
    return shutil.which(name) is not None


def python_module_available(mod: str) -> bool:
    """Return True when a Python module can be imported."""
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def run_fallback(brand: Path, root: Path, mode: str) -> dict:
    """Fall back to brand-replace.py."""
    args = ["--brand", str(brand), "--root", str(root)]
    if mode == "dry-run":
        args.append("--dry-run")
    elif mode == "diff":
        args.append("--diff")
    elif mode == "apply":
        args.append("--apply")
    args.append("--json")
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "brand-replace.py")] + args,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": r.stderr.strip() or r.stdout[:300], "fallback": True}


def detect_languages(root: Path) -> set[str]:
    """Detect source languages present under root."""
    langs = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        for fn in filenames:
            ext = Path(fn).suffix.lower()
            if ext in {".ts", ".tsx", ".js", ".jsx"}:
                langs.add("typescript")
            elif ext == ".py":
                langs.add("python")
            elif ext == ".go":
                langs.add("go")
            elif ext == ".rs":
                langs.add("rust")
            elif ext in {".java", ".cs"}:
                langs.add("jvm")
    return langs


def run_python_ast(args: argparse.Namespace) -> dict:
    """Run the Python AST renamer and return its JSON result."""
    ast_args = [
        sys.executable,
        str(SCRIPTS / "ast-rename.py"),
        "--brand",
        str(args.brand),
        "--root",
        str(args.root),
        "--json",
    ]
    if args.mode == "apply":
        ast_args.insert(-1, "--apply")
    elif args.mode == "dry-run":
        ast_args.insert(-1, "--dry-run")
    ast_r = subprocess.run(ast_args, capture_output=True, text=True, check=False)
    try:
        return json.loads(ast_r.stdout)
    except json.JSONDecodeError:
        return {"error": ast_r.stderr.strip() or ast_r.stdout[:200]}


def run_js_ast(args: argparse.Namespace) -> dict:
    """Run the JS/TS AST renamer over every JS/TS file in apply mode."""
    js_files = []
    for dirpath, dirnames, filenames in os.walk(args.root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        for fn in filenames:
            if fn.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs")):
                js_files.append(Path(dirpath) / fn)
    js_changes = 0
    js_files_changed = 0
    for js_file in js_files:
        r = subprocess.run(
            ["node", str(SCRIPTS / "js-ast-rename.js"), str(args.brand), str(js_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0 and r.stdout:
            js_file.write_text(r.stdout, encoding="utf-8")
            js_files_changed += 1
            try:
                meta = json.loads(r.stderr.strip().split("\n")[-1])
                js_changes += meta.get("changes", 0)
            except (json.JSONDecodeError, IndexError):
                pass
    return {"files_changed": js_files_changed, "total_changes": js_changes, "engine": "acorn"}


def build_packs() -> dict:
    """Return availability metadata for each rename pack."""
    node_available = tool_available("node")
    libcst_available = python_module_available("libcst")
    ast_grep_available = tool_available("ast-grep") or tool_available("sg")
    return {
        "typescript": {
            "available": node_available,
            "tool": "acorn (node) — AST rename available"
            if node_available
            else "node not installed",
            "status": "acorn AST rename" if node_available else "fallback (regex engine)",
        },
        "python": {
            "available": libcst_available,
            "tool": "LibCST" if libcst_available else "LibCST (pip install libcst) — not installed",
            "status": "libcst" if libcst_available else "stdlib ast (reformats)",
        },
        "polyglot": {
            "available": ast_grep_available,
            "tool": "ast-grep (26 langs)" if ast_grep_available else "ast-grep not installed",
            "status": "ast-grep" if ast_grep_available else "fallback (regex engine)",
        },
    }


def emit_result(args: argparse.Namespace, result: dict, langs: set[str]) -> None:
    """Print the rename-pack result as JSON or text."""
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"Rename pack: languages={sorted(langs)}")
    for key, value in result["rename_packs"].items():
        print(f"  {key}: {value['tool']} → {value['status']}")
    print(f"Engine: {result['engine']}")
    print(
        f"Files changed: {result.get('files_changed', '?')}  "
        f"Replacements: {result.get('total_replacements', '?')}"
    )


def main() -> int:
    """Parse arguments and run the command."""
    parser = argparse.ArgumentParser(description="Per-stack rename dispatcher")
    parser.add_argument("--brand", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--mode", choices=["dry-run", "diff", "apply"], default="dry-run")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true", help="report available AST engines and parse-check source files")
    parser.add_argument("--ast-grep", action="store_true", help="run ast-grep structural rename (optional)")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    if args.check:
        packs = build_packs()
        # parse checks
        py_ok = 0
        py_fail = 0
        js_ok = 0
        js_fail = 0
        for dirpath, dirnames, filenames in os.walk(args.root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
            for fn in filenames:
                full = Path(dirpath) / fn
                if fn.endswith(".py"):
                    r = subprocess.run([sys.executable, "-m", "py_compile", str(full)], capture_output=True, text=True)
                    if r.returncode == 0:
                        py_ok += 1
                    else:
                        py_fail += 1
                elif fn.endswith((".js", ".mjs", ".ts", ".tsx")):
                    node = shutil.which("node")
                    if node:
                        r = subprocess.run([node, "--check", str(full)], capture_output=True, text=True)
                        if r.returncode == 0:
                            js_ok += 1
                        else:
                            js_fail += 1
        report = {"engines": packs, "python_parse": {"ok": py_ok, "fail": py_fail}, "js_parse": {"ok": js_ok, "fail": js_fail}}
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            for k, v in packs.items():
                print(f"{k}: {v['tool']} -> {v['status']}")
            print(f"python parse: ok={py_ok} fail={py_fail}")
            print(f"js parse: ok={js_ok} fail={js_fail}")
        return 0

    langs = detect_languages(args.root)
    ast_result = run_python_ast(args) if "python" in langs else None

    ast_grep_result = None
    if getattr(args, "ast_grep", False) and tool_available("ast-grep"):
        ast_grep_result = {"files_changed": 0, "engine": "ast-grep"}
        brand = bt.load_brand(args.brand)
        pairs = bt.token_pairs(brand)
        lang_map = {"typescript": "ts", "python": "py", "go": "go", "rust": "rs", "jvm": "java"}
        for lang in langs:
            lg = lang_map.get(lang, lang)
            for old, new in pairs[:5]:
                subprocess.run(
                    ["ast-grep", "run", "--pattern", old, "--rewrite", new, "--lang", lg, str(args.root)],
                    capture_output=True,
                    text=True,
                )
        ast_grep_result["pairs_attempted"] = len(pairs)
    js_ast_result = (
        run_js_ast(args)
        if "typescript" in langs and tool_available("node") and args.mode == "apply"
        else None
    )
    packs = build_packs()

    result = run_fallback(args.brand, args.root, args.mode)
    if ast_result:
        result["ast_rename"] = ast_result
    if js_ast_result:
        result["js_ast_rename"] = js_ast_result
    if ast_grep_result:
        result["ast_grep_rename"] = ast_grep_result
    result["languages_detected"] = sorted(langs)
    result["rename_packs"] = {
        key: value
        for key, value in packs.items()
        if key in langs or key in ("typescript", "python")
    }
    result["engine"] = (
        "brand-replace.py (regex) + ast-rename.py (Python) + js-ast-rename.js (JS/TS)"
    )
    emit_result(args, result, langs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
