#!/usr/bin/env python3
"""Per-run state tracker (Tier 3): persist RALPH loop progress.

Writes `rebrands/STATE.json` so a session can resume mid-loop instead of
restarting. Tracks: current phase, step, last scan results, files done.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

DEFAULT_STATE = "STATE.json"


def load_state(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage rebrand run state (STATE.json)")
    parser.add_argument("--state", type=Path, default=Path(DEFAULT_STATE),
                        help="state file path (default: STATE.json in cwd)")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="initialize a new run")
    p_init.add_argument("--phase", default="intake", help="starting phase")
    p_init.add_argument("--repos", nargs="*", default=[], help="source repos")

    # set
    p_set = sub.add_parser("set", help="set a state field")
    p_set.add_argument("key", help="field name")
    p_set.add_argument("value", help="field value (JSON-parsed if possible)")

    # get
    p_get = sub.add_parser("get", help="get a state field")
    p_get.add_argument("key", help="field name")

    # step
    p_step = sub.add_parser("step", help="record a RALPH loop step result")
    p_step.add_argument("--step", type=int, required=True, help="step number")
    p_step.add_argument("--result", required=True, choices=["pass", "fail"],
                        help="step result")
    p_step.add_argument("--detail", default="", help="detail string")

    # show
    sub.add_parser("show", help="print current state")

    # clear
    sub.add_parser("clear", help="delete state file")

    args = parser.parse_args()
    path = args.state

    if args.command == "init":
        state = {
            "phase": args.phase,
            "repos": args.repos,
            "ralph_step": 0,
            "ralph_history": [],
            "files_done": [],
            "files_remaining": [],
        }
        save_state(path, state)
        print(f"State initialized: {path}")
        return 0

    if args.command == "clear":
        if path.exists():
            path.unlink()
            print(f"State cleared: {path}")
        return 0

    state = load_state(path)
    if not state and args.command != "show":
        print("No state file found. Run 'state.py init' first.", file=sys.stderr)
        return 2

    if args.command == "show":
        print(json.dumps(state, indent=2))
        return 0

    if args.command == "set":
        try:
            val = json.loads(args.value)
        except json.JSONDecodeError:
            val = args.value
        state[args.key] = val
        save_state(path, state)
        print(f"Set {args.key} = {val}")
        return 0

    if args.command == "get":
        val = state.get(args.key)
        if val is None:
            print(f"{args.key}: (not set)")
            return 1
        print(json.dumps(val) if not isinstance(val, str) else val)
        return 0

    if args.command == "step":
        history = state.setdefault("ralph_history", [])
        history.append({
            "step": args.step,
            "result": args.result,
            "detail": args.detail,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        state["ralph_step"] = args.step
        state["last_result"] = args.result
        save_state(path, state)
        print(f"Recorded step {args.step}: {args.result}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
PY