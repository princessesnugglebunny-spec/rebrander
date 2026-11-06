#!/usr/bin/env python3
"""Generate brand placeholder assets and apply theme colors (P1 visual pass).

Produces SVG wordmark, favicon, and logo placeholders derived from brand.json
(colors + name) so a rebranded project has consistent visual identity even
before real designer assets arrive. Also does a best-effort theme-color swap
in CSS/SCSS/JSON/YAML files using original.colors -> target.colors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt


def _svg_wordmark(name: str, primary: str, accent: str) -> str:
    safe = name.replace("&", "&amp;").replace("<", "&lt;")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 80" width="320" height="80">
  <rect width="320" height="80" rx="12" fill="{primary}"/>
  <text x="160" y="52" font-family="system-ui, -apple-system, sans-serif"
        font-size="30" font-weight="700" fill="{accent}" text-anchor="middle">{safe}</text>
</svg>
"""


def _svg_favicon(letter: str, primary: str, accent: str) -> str:
    safe = letter[:1].upper().replace("&", "&amp;")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <rect width="64" height="64" rx="14" fill="{primary}"/>
  <text x="32" y="46" font-family="system-ui, -apple-system, sans-serif"
        font-size="36" font-weight="800" fill="{accent}" text-anchor="middle">{safe}</text>
</svg>
"""


def _svg_logo(name: str, primary: str, accent: str) -> str:
    safe = name.replace("&", "&amp;").replace("<", "&lt;")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <rect width="200" height="200" rx="32" fill="{primary}"/>
  <circle cx="100" cy="80" r="40" fill="{accent}" opacity="0.9"/>
  <text x="100" y="160" font-family="system-ui, -apple-system, sans-serif"
        font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{safe}</text>
</svg>
"""


def generate_assets(brand: dict, out_dir: Path) -> List[str]:
    """Write SVG placeholders; return list of created files."""
    target = brand.get("target", {})
    name = target.get("name", "Brand")
    colors = target.get("colors", {})
    primary = colors.get("primary", "#1f2937")
    accent = colors.get("accent", "#ffffff")
    out_dir.mkdir(parents=True, exist_ok=True)
    created = []
    files = {
        "wordmark.svg": _svg_wordmark(name, primary, accent),
        "favicon.svg": _svg_favicon(name, primary, accent),
        "logo.svg": _svg_logo(name, primary, accent),
    }
    for fn, content in files.items():
        path = out_dir / fn
        path.write_text(content, encoding="utf-8")
        created.append(str(path))
    return created


def swap_theme_colors(root: Path, original_colors: Dict, target_colors: Dict) -> int:
    """Best-effort hex color swap in CSS/SCSS/JSON/YAML files. Returns count."""
    if not original_colors or not target_colors:
        return 0
    # Build old->new map (case-insensitive).
    mapping = {}
    for k, v in original_colors.items():
        if k in target_colors and isinstance(v, str) and isinstance(target_colors[k], str):
            mapping[v.lower()] = target_colors[k]
    if not mapping:
        return 0
    count = 0
    exts = {".css", ".scss", ".less", ".json", ".yaml", ".yml", ".html", ".tsx", ".jsx"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        for fn in filenames:
            if Path(fn).suffix.lower() not in exts:
                continue
            full = Path(dirpath) / fn
            try:
                text = full.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            new = text
            for old, newc in mapping.items():
                new = new.replace(old, newc).replace(old.upper(), newc.upper())
            if new != text:
                full.write_text(new, encoding="utf-8")
                count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate brand placeholder assets + theme swap")
    parser.add_argument("--brand", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path, help="project root")
    parser.add_argument("--assets-dir", default="assets", help="relative assets dir (default: assets)")
    parser.add_argument("--swap-colors", action="store_true", help="also swap theme colors in source")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    brand = bt.load_brand(args.brand)
    target = brand.get("target", {})
    original_colors = brand.get("original", {}).get("colors", {})
    target_colors = target.get("colors", {})

    out_dir = args.root / args.assets_dir
    created = generate_assets(brand, out_dir)

    swapped = 0
    if args.swap_colors:
        swapped = swap_theme_colors(args.root, original_colors, target_colors)

    if args.json:
        print(json.dumps({"created": created, "theme_files_swapped": swapped}, indent=2))
    else:
        print(f"Generated {len(created)} asset(s) in {out_dir}:")
        for c in created:
            print(f"  {c}")
        if args.swap_colors:
            print(f"Theme color swap touched {swapped} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
