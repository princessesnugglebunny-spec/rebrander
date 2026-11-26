"""Headless-browser verification (SRP: verification only). Optional playwright."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402


def main() -> int:
    """Parse arguments and run browser checks."""
    parser = argparse.ArgumentParser(description="Headless browser verification")
    parser.add_argument("--url", required=True)
    parser.add_argument("--brand", type=Path, required=True)
    parser.add_argument("--shots", type=Path, default=Path(".relabel/verify"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed; skipping browser verification.", file=sys.stderr)
        if args.json:
            print(json.dumps({"skipped": True, "reason": "playwright not installed"}))
        return 0

    brand = bt.load_brand(args.brand)
    target_name = brand.get("target", {}).get("name", "")
    old_variants = bt.residual_variants(list(brand.get("original", {}).values()))
    args.shots.mkdir(parents=True, exist_ok=True)

    results = []
    console_errors = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp in ({"width": 1440, "height": 980}, {"width": 390, "height": 844}):
            page = browser.new_page(viewport=vp)
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            try:
                page.goto(args.url, wait_until="networkidle", timeout=30000)
            except Exception as exc:
                page_errors.append(str(exc))
            title = page.title()
            text = page.inner_text("body")
            html = page.content()
            scroll_w = page.evaluate("() => document.documentElement.scrollWidth")
            inner_w = page.evaluate("() => window.innerWidth")
            shot = args.shots / ("desktop.png" if vp["width"] == 1440 else "mobile.png")
            page.screenshot(path=str(shot))

            # checks
            results.append({"id": "brand-title", "viewport": vp, "pass": target_name.lower() in title.lower()})
            old_hits = [v for v in old_variants if v in (text + " " + html).lower()]
            results.append({"id": "brand-strings", "viewport": vp, "pass": len(old_hits) == 0, "hits": old_hits[:5]})
            results.append({"id": "overflow", "viewport": vp, "pass": (scroll_w - inner_w) <= 0})
        browser.close()

    results.append({"id": "console-errors", "pass": len(console_errors) == 0 and len(page_errors) == 0, "count": len(console_errors) + len(page_errors)})
    results.append({"id": "screenshots", "pass": True})

    failed = [r for r in results if not r.get("pass", True)]
    if args.json:
        print(json.dumps({"checks": results, "failed": len(failed)}, indent=2))
    else:
        for r in results:
            print(f"{'PASS' if r.get('pass') else 'FAIL'} {r['id']} {r.get('viewport', '')}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
