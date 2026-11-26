"""Compare two capture JSONs (SRP: comparison only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402


def main() -> int:
    """Parse arguments and compare."""
    parser = argparse.ArgumentParser(description="Compare two captures")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    ref = json.loads(args.reference.read_text())
    cand = json.loads(args.candidate.read_text())

    matches = []
    differences = []
    # exit code
    if ref.get("exit_code") == cand.get("exit_code"):
        matches.append("exit_code")
    else:
        differences.append({"field": "exit_code", "reference": ref.get("exit_code"), "candidate": cand.get("exit_code")})
    # stdout
    if ref.get("stdout") == cand.get("stdout"):
        matches.append("stdout")
    else:
        differences.append({"field": "stdout", "reference": ref.get("stdout", "")[:200], "candidate": cand.get("stdout", "")[:200]})
    # file hashes
    ref_hashes = ref.get("file_hashes", {})
    cand_hashes = cand.get("candidate_file_hashes", cand.get("file_hashes", {}))
    common = set(ref_hashes) & set(cand_hashes)
    changed_files = [f for f in common if ref_hashes[f] != cand_hashes[f]]
    unknown = [f for f in ref_hashes if f not in cand_hashes]

    report = {
        "scenario_reference": ref.get("scenario"),
        "scenario_candidate": cand.get("scenario"),
        "matches": matches,
        "differences": differences,
        "changed_files": changed_files,
        "unknown_files": unknown,
        "coverage": {
            "common_files": len(common),
            "changed_files": len(changed_files),
            "unknown_files": len(unknown),
        },
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Matches: {matches}")
        print(f"Differences: {len(differences)}")
        print(f"Changed files: {len(changed_files)}")
        print(f"Unknown files: {len(unknown)}")
    if args.out:
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 1 if differences or changed_files else 0


if __name__ == "__main__":
    sys.exit(main())
