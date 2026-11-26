"""Tiny two-tier (memory + disk) cache with graceful quota failure.

Used by inventory, brand-replace and source-scan to skip unchanged work.
Mirrors the analysis-cache pattern: memory first, disk best-effort, never
raise on cache errors.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

MEMORY: Dict[str, Any] = {}


def _key(namespace: str, payload: str) -> str:
    """Build a stable cache key from namespace + payload."""
    return f"{namespace}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def get(namespace: str, payload: str) -> Optional[Any]:
    """Return cached value or None on miss/error."""
    key = _key(namespace, payload)
    if key in MEMORY:
        return MEMORY[key]
    cache_file = _cache_file(key)
    if cache_file and cache_file.exists():
        try:
            value = json.loads(cache_file.read_text(encoding="utf-8"))
            MEMORY[key] = value
            return value
        except (json.JSONDecodeError, OSError):
            return None
    return None


def set(namespace: str, payload: str, value: Any) -> None:
    """Store value in memory and best-effort on disk."""
    key = _key(namespace, payload)
    MEMORY[key] = value
    cache_file = _cache_file(key)
    if cache_file is None:
        return
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(value), encoding="utf-8")
    except OSError:
        pass  # quota or permission issue — memory cache still works


def invalidate(namespace: str, payload: str) -> None:
    """Remove a cached entry."""
    key = _key(namespace, payload)
    MEMORY.pop(key, None)
    cache_file = _cache_file(key)
    if cache_file and cache_file.exists():
        try:
            cache_file.unlink()
        except OSError:
            pass


def tree_hash(root: Path) -> str:
    """Hash of file paths + mtimes + sizes under root (fast change detection)."""
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            try:
                st = path.stat()
                h.update(str(path.relative_to(root)).encode("utf-8"))
                h.update(str(st.st_mtime_ns).encode())
                h.update(str(st.st_size).encode())
            except OSError:
                continue
    return h.hexdigest()


def _cache_file(key: str) -> Optional[Path]:
    """Return a disk cache path for key, or None if not writable."""
    base = Path.home() / ".cache" / "rebrander"
    try:
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{key.replace(':', '_')}.json"
    except OSError:
        return None


def main() -> int:
    """Minimal CLI for cache inspection/clearing."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage rebrander cache")
    parser.add_argument("--clear", action="store_true", help="clear all cached entries")
    parser.add_argument("--version", action="version", version="rebrander 1.1.0")
    args = parser.parse_args()
    if args.clear:
        base = Path.home() / ".cache" / "rebrander"
        count = 0
        if base.exists():
            for f in base.glob("*.json"):
                try:
                    f.unlink()
                    count += 1
                except OSError:
                    pass
        print(f"Cleared {count} cache file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
