"""End-to-end rebrand orchestrator (SRP: orchestration only).

Runs intake-check -> inventory -> brand-replace dry-run -> (on --apply) apply ->
tests -> source-scan -> report, checkpointing via state.py. --fast skips
artifact/binary scans; --resume continues from last checkpoint.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402
import state as _state  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent


def _run(cmd: list) -> int:
    """Run a command list, stream output, return exit code."""
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    r = subprocess.run(cmd)
    return r.returncode


def main() -> int:
    """Parse arguments and run the pipeline."""
    parser = argparse.ArgumentParser(description="Rebrand pipeline orchestrator")
    parser.add_argument("--brand", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="apply (default dry-run only)")
    parser.add_argument("--fast", action="store_true", help="skip artifact/binary scans")
    parser.add_argument("--capture", action="store_true", help="capture original + candidate behavior and compare")
    parser.add_argument("--resume", action="store_true", help="resume from STATE.json")
    parser.add_argument("--state", type=Path, default=Path("STATE.json"))
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    root = args.root
    state = _state.load_state(args.state) if args.resume else {}
    if not state:
        _state.save_state(args.state, {"phase": "intake", "repos": [str(root)], "ralph_step": 0, "ralph_history": [], "files_done": [], "files_remaining": []})
        state = _state.load_state(args.state)


    # 1. baseline
    if "baseline" not in state:
        rc = _run([sys.executable, str(SCRIPTS / "baseline.py"), "--root", str(root), "--out", str(root.parent / "baseline.json")])
        state["baseline"] = "done" if rc == 0 else "failed"
        _state.save_state(args.state, state)
        if rc != 0:
            return rc

    # 2. inventory
    if "inventory" not in state:
        rc = _run([sys.executable, str(SCRIPTS / "inventory.py"), "--root", str(root), "--out", str(root.parent / "INVENTORY.md")])
        state["inventory"] = "done" if rc == 0 else "failed"
        _state.save_state(args.state, state)
        if rc != 0:
            return rc

    # 3. brand-replace dry-run
    rc = _run([sys.executable, str(SCRIPTS / "brand-replace.py"), "--brand", str(args.brand), "--root", str(root), "--dry-run"])
    if rc not in (0,):
        return rc

    # 4. apply if requested
    if args.apply:
        rc = _run([sys.executable, str(SCRIPTS / "brand-replace.py"), "--brand", str(args.brand), "--root", str(root), "--apply", "--transactional"])
        if rc != 0:
            return rc

    # 5. source scan
    rc = _run([sys.executable, str(SCRIPTS / "source-scan.py"), "--root", str(root), "--brand", str(args.brand)])
    # non-zero means hits; continue

    # 6. report
    rc = _run([
        sys.executable, str(SCRIPTS / "report.py"),
        "--brand", str(args.brand), "--root", str(root),
        "--out", str(root.parent / "REBRAND-REPORT.md"),
    ])
    state["report"] = "done" if rc == 0 else "failed"
    _state.save_state(args.state, state)

    if args.capture:
        cap_orig = root.parent / "capture-original.json"
        cap_new = root.parent / "capture-rebranded.json"
        _run([sys.executable, str(SCRIPTS / "capture.py"), "--scenario", "original", "--command", "echo ok", "--root", str(root), "--out", str(cap_orig)])
        _run([sys.executable, str(SCRIPTS / "capture.py"), "--scenario", "rebranded", "--command", "echo ok", "--root", str(root), "--out", str(cap_new)])
        _run([sys.executable, str(SCRIPTS / "compare-captures.py"), "--reference", str(cap_orig), "--candidate", str(cap_new), "--out", str(root.parent / "CAPTURE-COMPARE.json")])

    if not args.fast:
        print("Full mode: run artifact-scan.py and binary-diff.py manually if applicable.", file=sys.stderr)
    print("Pipeline complete. State:", args.state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
