"""Environment doctor (SRP: environment check only)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402


def check(name: str, fn) -> dict:
    """Run a check function and return status dict."""
    try:
        ok, detail = fn()
    except Exception as exc:
        ok, detail = False, str(exc)
    return {"name": name, "ok": bool(ok), "detail": detail}


def main() -> int:
    """Parse arguments and run checks."""
    parser = argparse.ArgumentParser(description="Check rebrander environment")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    def has_exe(n):
        p = shutil.which(n)
        return (p is not None, p or "not found")

    def py_mod(m):
        try:
            __import__(m)
            return True, "installed"
        except ImportError:
            return False, "not installed"

    checks = [
        check("python", lambda: (True, sys.version.split()[0])),
        check("git", lambda: has_exe("git")),
        check("ripgrep", lambda: has_exe("rg")),
        check("node", lambda: has_exe("node")),
        check("playwright", lambda: py_mod("playwright")),
        check("chromium", lambda: has_exe("chromium") or has_exe("chromium-browser") or has_exe("google-chrome")),
        check("jsonschema", lambda: py_mod("jsonschema")),
        check("libcst", lambda: py_mod("libcst")),
    ]
    # venv
    venv = Path.home() / ".local/share/rebrander/venv"
    checks.append(check("ablation-venv", lambda: (venv.exists(), str(venv) if venv.exists() else "missing")))

    failed = [c for c in checks if not c["ok"] and c["name"] in ("python", "git")]
    if args.json:
        print(json.dumps({"checks": checks, "required_failed": len(failed)}, indent=2))
    else:
        for c in checks:
            print(f"{'OK ' if c['ok'] else 'NO '} {c['name']}: {c['detail']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
