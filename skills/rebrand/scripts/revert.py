#!/usr/bin/env python3
"""One-command revert (P2): undo a rebrand attempt using git.

Snapshots each attempt on a dedicated branch so the original source is never
lost. Revert restores the working tree to the pre-rebrand state.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root)] + list(args),
        capture_output=True, text=True, check=False,
    )


def is_git_repo(root: Path) -> bool:
    r = git(root, "rev-parse", "--is-inside-work-tree")
    return r.returncode == 0 and r.stdout.strip() == "true"


def main() -> int:
    parser = argparse.ArgumentParser(description="Revert a rebrand attempt")
    parser.add_argument("--root", required=True, type=Path, help="rebranded repo root")
    parser.add_argument("--branch", default="rebrand/original", help="branch to restore (default: rebrand/original)")
    parser.add_argument("--stash", action="store_true", help="stash current changes instead of hard reset")
    parser.add_argument("--file", help="restore a single file from the original branch instead of the whole tree")
    parser.add_argument("--list", action="store_true", help="list available rebrand branches")
    parser.add_argument("--version", action="version", version="rebrander 1.0.0")
    args = parser.parse_args()

    root = args.root.resolve()
    if not is_git_repo(root):
        print(f"ERROR: {root} is not a git repository. Revert requires git.", file=sys.stderr)
        return 2

    if args.list:
        r = git(root, "branch", "-a")
        print("Available branches:")
        print(r.stdout)
        return 0

    if args.file:
        r = git(root, "checkout", args.branch, "--", args.file)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            return 4
        print(f"Restored {args.file} from {args.branch}.")
        return 0

    # Ensure the original branch exists.
    check = git(root, "rev-parse", "--verify", args.branch)
    if check.returncode != 0:
        # Try to find the original default branch.
        r = git(root, "symbolic-ref", "refs/remotes/origin/HEAD")
        default = r.stdout.strip().replace("refs/remotes/origin/", "") if r.returncode == 0 else "main"
        print(f"Branch '{args.branch}' not found. Available branches:")
        git(root, "branch", "-a")
        print(f"Hint: use --branch <name> or create '{args.branch}' before rebranding.")
        return 3

    if args.stash:
        r = git(root, "stash", "push", "-m", "rebrand-revert-stash")
        print(r.stdout.strip() or r.stderr.strip())
        r = git(root, "checkout", args.branch)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            return 4
        print(f"Reverted to {args.branch} (previous changes stashed).")
    else:
        r = git(root, "checkout", args.branch)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            return 4
        r = git(root, "reset", "--hard", args.branch)
        print(r.stdout.strip() or r.stderr.strip())
        print(f"Reverted to {args.branch} (hard reset).")

    # Clean up rebrand artifacts.
    for artifact in ("brand.json", "removal-log.json", ".rubric.json"):
        p = root / artifact
        if p.exists():
            p.unlink()
            print(f"Removed {artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
