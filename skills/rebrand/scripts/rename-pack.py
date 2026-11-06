#!/usr/bin/env python3
"""Per-stack rename packs (P2): dispatch to the best available tool per language.

Tries language-specific AST-aware renamers (ts-morph for TS/JS, LibCST for
Python) when installed; falls back to the regex-based brand-replace.py engine
so the pipeline always works without extra dependencies.
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

SCRIPTS = Path(__file__).resolve().parent


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def python_module_available(mod: str) -> bool:
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
        capture_output=True, text=True, check=False,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": r.stderr.strip() or r.stdout[:300], "fallback": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-stack rename dispatcher")
    parser.add_argument("--brand", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--mode", choices=["dry-run", "diff", "apply"], default="dry-run")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    brand = bt.load_brand(args.brand)
    # Determine which languages are present.
    langs = set()
    for dirpath, dirnames, filenames in __import__("os").walk(args.root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        for fn in filenames:
            ext = Path(fn).suffix.lower()
            if ext in {".ts", ".tsx", ".js", ".jsx"}:
                langs.add("typescript")
            elif ext == ".py":
                langs.add("python")
            elif ext in {".go"}:
                langs.add("go")
            elif ext in {".rs"}:
                langs.add("rust")
            elif ext in {".java", ".cs"}:
                langs.add("jvm")

    # Run Python AST rename first (more precise for .py files).
    ast_result = None
    if "python" in langs:
        ast_r = subprocess.run(
            [sys.executable, str(SCRIPTS / "ast-rename.py"),
             "--brand", str(args.brand), "--root", str(args.root),
             "--apply", "--json"],
            capture_output=True, text=True, check=False,
        )
        try:
            ast_result = json.loads(ast_r.stdout)
        except json.JSONDecodeError:
            ast_result = {"error": ast_r.stderr.strip() or ast_r.stdout[:200]}

    packs = {
        "typescript": {
            "available": tool_available("node"),
            "tool": "acorn (node) — AST rename available" if tool_available("node") else "node not installed",
            "status": "acorn AST rename" if tool_available("node") else "fallback (regex engine)",
        },
        "python": {
            "available": python_module_available("libcst"),
            "tool": "LibCST" if python_module_available("libcst") else "LibCST (pip install libcst) — not installed",
            "status": "libcst" if python_module_available("libcst") else "stdlib ast (reformats)",
        },
    }

    # Run JS/TS AST rename via node + acorn (when available).
    js_ast_result = None
    if "typescript" in langs and tool_available("node"):
        js_files = []
        for dirpath, dirnames, filenames in os.walk(args.root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
            for fn in filenames:
                if fn.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs")):
                    js_files.append(Path(dirpath) / fn)
        js_changes = 0
        js_files_changed = 0
        for jf in js_files:
            r = subprocess.run(
                ["node", str(SCRIPTS / "js-ast-rename.js"), str(args.brand), str(jf)],
                capture_output=True, text=True, check=False,
            )
            if r.returncode == 0 and r.stdout:
                jf.write_text(r.stdout, encoding="utf-8")
                js_files_changed += 1
                try:
                    meta = json.loads(r.stderr.strip().split("\n")[-1])
                    js_changes += meta.get("changes", 0)
                except (json.JSONDecodeError, IndexError):
                    pass
        js_ast_result = {"files_changed": js_files_changed, "total_changes": js_changes, "engine": "acorn"}

    result = run_fallback(args.brand, args.root, args.mode)
    if ast_result:
        result["ast_rename"] = ast_result
    if js_ast_result:
        result["js_ast_rename"] = js_ast_result
    result["languages_detected"] = sorted(langs)
    result["rename_packs"] = {k: v for k, v in packs.items() if k in langs or k in ("typescript", "python")}
    result["engine"] = "brand-replace.py (regex) + ast-rename.py (Python) + js-ast-rename.js (JS/TS)"

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Rename pack: languages={sorted(langs)}")
        for k, v in result["rename_packs"].items():
            print(f"  {k}: {v['tool']} → {v['status']}")
        print(f"Engine: {result['engine']}")
        print(f"Files changed: {result.get('files_changed', '?')}  "
              f"Replacements: {result.get('total_replacements', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
