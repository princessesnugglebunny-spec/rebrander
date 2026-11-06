#!/usr/bin/env python3
"""Python AST-aware identifier renamer (Tier 2).

Uses LibCST when available (preserves formatting) or stdlib `ast` as fallback
(reformats). Both are more precise than regex for Python code — won't touch
identifiers inside strings or comments unless they match the token exactly.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt

# Try LibCST (preferred: preserves formatting).
try:
    import libcst as cst
    import libcst.matchers as m
    _LIBCST_AVAILABLE = True
except ImportError:
    _LIBCST_AVAILABLE = False


class _LibCSTRenamer(cst.CSTTransformer):
    """LibCST transformer that renames identifiers."""

    def __init__(self, pairs: List[Tuple[str, str]]):
        self.pairs = dict(pairs)
        self.changes = 0

    def leave_Name(self, original_node, updated_node):
        if updated_node.value in self.pairs:
            self.changes += 1
            return updated_node.with_changes(value=self.pairs[updated_node.value])
        return updated_node

    def leave_FunctionDef(self, original_node, updated_node):
        if updated_node.name.value in self.pairs:
            self.changes += 1
            return updated_node.with_changes(
                name=updated_node.name.with_changes(value=self.pairs[updated_node.name.value])
            )
        return updated_node

    def leave_ClassDef(self, original_node, updated_node):
        if updated_node.name.value in self.pairs:
            self.changes += 1
            return updated_node.with_changes(
                name=updated_node.name.with_changes(value=self.pairs[updated_node.name.value])
            )
        return updated_node

    def leave_Attribute(self, original_node, updated_node):
        if updated_node.attr.value in self.pairs:
            self.changes += 1
            return updated_node.with_changes(
                attr=updated_node.attr.with_changes(value=self.pairs[updated_node.attr.value])
            )
        return updated_node


def rename_with_libcst(source: str, pairs: List[Tuple[str, str]]) -> Tuple[str, int]:
    """Rename using LibCST (preserves formatting)."""
    tree = cst.parse_module(source)
    renamer = _LibCSTRenamer(pairs)
    new_tree = tree.visit(renamer)
    return new_tree.code, renamer.changes


class _ASTRenamer(ast.NodeTransformer):
    """Stdlib AST renamer (reformats code)."""

    def __init__(self, pairs: List[Tuple[str, str]]):
        self.pairs = dict(pairs)
        self.changes = 0

    def _rename(self, name: str) -> str:
        if name in self.pairs:
            self.changes += 1
            return self.pairs[name]
        return name

    def visit_Name(self, node):
        node.id = self._rename(node.id)
        return node

    def visit_FunctionDef(self, node):
        node.name = self._rename(node.name)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        node.name = self._rename(node.name)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node):
        node.name = self._rename(node.name)
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node):
        node.attr = self._rename(node.attr)
        self.generic_visit(node)
        return node

    def visit_arg(self, node):
        node.arg = self._rename(node.arg)
        self.generic_visit(node)
        return node


def rename_with_ast(source: str, pairs: List[Tuple[str, str]]) -> Tuple[str, int]:
    """Rename using stdlib ast (reformats code)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, 0

    renamer = _ASTRenamer(pairs)
    new_tree = renamer.visit(tree)
    ast.fix_missing_locations(new_tree)

    try:
        new_source = ast.unparse(new_tree)
    except Exception:
        return source, 0

    return new_source, renamer.changes


def rename_python_file(path: Path, pairs: List[Tuple[str, str]]) -> Tuple[str, int, str]:
    """Rename identifiers in a Python file. Returns (new_source, change_count, engine)."""
    source = path.read_text(encoding="utf-8")

    if _LIBCST_AVAILABLE:
        try:
            new_source, changes = rename_with_libcst(source, pairs)
            return new_source, changes, "libcst"
        except Exception:
            pass

    new_source, changes = rename_with_ast(source, pairs)
    return new_source, changes, "ast"


def main() -> int:
    parser = argparse.ArgumentParser(description="Python AST-aware identifier renamer")
    parser.add_argument("--brand", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    brand = bt.load_brand(args.brand)
    pairs = bt.token_pairs(brand)

    # Filter to valid Python identifiers.
    id_pairs = [(o, n) for o, n in pairs if o.isidentifier()]

    if not id_pairs:
        print("No identifier-compatible token pairs found.", file=sys.stderr)
        return 2

    import os
    py_files = []
    for dirpath, dirnames, filenames in os.walk(args.root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        for fn in filenames:
            if fn.endswith(".py"):
                py_files.append(Path(dirpath) / fn)

    results = []
    total_changes = 0
    engines_used: Dict[str, int] = {}
    for path in sorted(py_files):
        new_source, changes, engine = rename_python_file(path, id_pairs)
        if changes > 0:
            total_changes += changes
            engines_used[engine] = engines_used.get(engine, 0) + 1
            rel = str(path.relative_to(args.root))
            results.append({"file": rel, "changes": changes, "engine": engine})
            if args.apply:
                path.write_text(new_source, encoding="utf-8")

    if args.json:
        print(json.dumps({
            "files_changed": len(results),
            "total_changes": total_changes,
            "engines": engines_used,
            "files": results,
            "libcst_available": _LIBCST_AVAILABLE,
        }, indent=2))
    else:
        print(f"AST rename: {len(results)} file(s), {total_changes} identifier(s) renamed")
        print(f"  engines: {engines_used}  libcst: {_LIBCST_AVAILABLE}")
        for r in results:
            print(f"  {r['changes']:4d}  {r['file']}  ({r['engine']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY