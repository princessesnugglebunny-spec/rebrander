#!/usr/bin/env python3
"""DocIN-style binary diff runbook (SRP: version_delta wrapper).

Compares a function across a pre-rebrand and post-rebrand build using
Ablation's `version_delta.VersionTracker` to produce a homolog match and a
unified diff. Used by the RALPH loop to prove only branding changed.

Requires `pip install 'ablation-tool[full]'` (angr + Capstone). If the full
extras are missing, the script exits with a clear install hint instead of
crashing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from ablation.analyzers.version_delta import VersionTracker
    _AVAILABLE = True
except Exception as exc:  # noqa: BLE001
    _AVAILABLE = False
    _IMPORT_ERROR = str(exc)

try:
    import angr  # noqa: F401
    _ANGR = True
except Exception:  # noqa: BLE001
    _ANGR = False


def main() -> int:
    parser = argparse.ArgumentParser(description="Binary diff pre/post rebrand (DocIN)")
    parser.add_argument("--before", required=True, type=Path, help="pre-rebrand binary")
    parser.add_argument("--after", required=True, type=Path, help="post-rebrand binary")
    parser.add_argument("--seed-va", required=True, help="seed function virtual address (hex, e.g. 0x1000)")
    parser.add_argument("--seed-name", required=True, help="seed function name")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    if not _AVAILABLE:
        msg = ("Ablation version_delta unavailable. Install the full extras: "
               "pip install 'ablation-tool[full]'  (angr + Capstone). "
               f"Import error: {_IMPORT_ERROR}")
        if args.json:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return 2

    if not _ANGR:
        msg = ("angr is not installed, so binary diffing cannot run. "
               "Install the full extras: pip install 'ablation-tool[full]'")
        if args.json:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return 2

    seed_va = int(args.seed_va, 0)
    tracker = VersionTracker(binaries={"before": str(args.before), "after": str(args.after)})
    try:
        reports = tracker.track(seed_binary="before", seed_va=seed_va, seed_name=args.seed_name)
    except Exception as exc:  # noqa: BLE001
        msg = f"track() failed: {exc}"
        if args.json:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        return 3

    out: Dict[str, Any] = {"seed": args.seed_name, "seed_va": hex(seed_va), "reports": []}
    for rep in reports:
        entry: Dict[str, Any] = {"summary": rep.summary()}
        m = getattr(rep, "match", None)
        if m is not None:
            entry["match"] = {
                "target": getattr(m, "target", None),
                "confidence": getattr(m, "confidence", None),
                "jaccard": getattr(m, "jaccard", None),
                "semantic_score": getattr(m, "semantic_score", None),
                "new_callees": getattr(m, "new_callees", None),
                "removed_callees": getattr(m, "removed_callees", None),
            }
            delta = getattr(m, "delta", None)
            if delta is not None and hasattr(delta, "unified_diff"):
                try:
                    entry["unified_diff"] = delta.unified_diff("before", "after")
                except Exception as exc:  # noqa: BLE001
                    entry["diff_error"] = str(exc)
        out["reports"].append(entry)

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for entry in out["reports"]:
            print("=" * 70)
            print(entry["summary"])
            m = entry.get("match")
            if m:
                print(f"confidence={m['confidence']} jaccard={m['jaccard']} "
                      f"semantic={m['semantic_score']}")
                print(f"new callees: {m['new_callees']}")
                print(f"removed callees: {m['removed_callees']}")
                if "unified_diff" in entry:
                    print("-" * 70)
                    print(entry["unified_diff"])
            else:
                print("No homolog match found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
