#!/usr/bin/env python3
"""DocIN-style binary diff runbook (SRP: version_delta wrapper).

Compares a function across a pre-rebrand and post-rebrand build using
Ablation's `version_delta.VersionTracker` to produce a homolog match and a
unified diff. Used by the RALPH loop to prove only branding changed.

The verified stack is isolated in ``~/.local/share/rebrander/venv`` because
Ablation 2.93 targets the angr 9.2 API while recent angr releases removed
``Function.callees``/``Function.call_sites``. When the current interpreter
cannot import the stack, this script re-execs itself under that venv.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_tokens as bt  # noqa: E402

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

FULL_PYTHON_ENV = "REBRANDER_FULL_PYTHON"
BOOTSTRAP_ENV = "REBRANDER_BINARY_BOOTSTRAPPED"
DEFAULT_FULL_PYTHON = Path.home() / ".local/share/rebrander/venv/bin/python"

try:
    import angr  # noqa: F401

    _ANGR = True
    _ANGR_ERROR = ""
except Exception as exc:  # noqa: BLE001
    _ANGR = False
    _ANGR_ERROR = str(exc)

try:
    from ablation.analyzers.version_delta import VersionTracker

    _AVAILABLE = True
    _IMPORT_ERROR = ""
except Exception as exc:  # noqa: BLE001
    _AVAILABLE = False
    _IMPORT_ERROR = str(exc)


def _full_python() -> Optional[str]:
    """Return the verified binary-analysis interpreter, if one is installed."""
    candidate = os.environ.get(FULL_PYTHON_ENV)
    if candidate and Path(candidate).exists():
        return candidate
    if DEFAULT_FULL_PYTHON.exists():
        return str(DEFAULT_FULL_PYTHON)
    return None


def _maybe_reexec() -> None:
    """Re-exec under the verified venv when the current interpreter lacks the stack."""
    if os.environ.get(BOOTSTRAP_ENV) == "1":
        return
    if _AVAILABLE and _ANGR:
        return
    full = _full_python()
    if not full:
        return
    # Compare paths, not resolved targets: a venv's bin/python is a symlink to
    # the base interpreter, so resolve() would make the two look identical.
    if os.path.abspath(full) == os.path.abspath(sys.executable):
        return
    env = os.environ.copy()
    env[BOOTSTRAP_ENV] = "1"
    os.execve(full, [full, str(Path(__file__).resolve()), *sys.argv[1:]], env)


def _features_from_angr(vd, cls, cfg, va: int, name: str = ""):
    """Build FuncFeatures from an angr CFG using version-tolerant APIs."""
    func = cfg.kb.functions.get(va) or cfg.kb.functions.floor_func(va)
    if func is None:
        return None
    blocks = list(func.blocks)
    n_edges = 0
    for block in blocks:
        try:
            if block in func.graph:
                n_edges += len(list(func.graph.successors(block)))
        except Exception:  # noqa: BLE001
            continue
    mnemonics: List[str] = []
    norm_lines: List[str] = []
    for block in sorted(blocks, key=lambda b: b.addr):
        disasm = block.disassembly
        if disasm is None:
            continue
        for insn in disasm.insns:
            raw = f"{insn.mnemonic} {insn.op_str}".strip()
            mnemonics.append(insn.mnemonic.lower())
            normalized = vd._normalize_line(raw)
            if normalized:
                norm_lines.append(normalized)
    callees: List[str] = []
    try:
        for callee_addr in cfg.kb.functions.callgraph.successors(func.addr):
            callee = cfg.kb.functions.get(callee_addr)
            callees.append(vd.categorize_callee(callee.name if callee else hex(callee_addr)))
    except Exception:  # noqa: BLE001
        pass
    string_xrefs: List[str] = []
    try:
        for ref in cfg.memory_data.values():
            if ref.sort == "string" and ref.content:
                value = ref.content.decode(errors="replace").strip()
                if value:
                    string_xrefs.append(value[:80])
    except Exception:  # noqa: BLE001
        pass
    return cls(
        va=va,
        name=name or func.name or hex(va),
        n_blocks=len(blocks),
        n_edges=n_edges,
        n_instrs=len(mnemonics),
        mnemonics=mnemonics,
        ngrams_4=vd._ngrams(mnemonics, 4),
        norm_lines=norm_lines,
        callees=callees,
        string_xrefs=string_xrefs,
    )


def _install_from_angr_shim() -> None:
    """Install a compatibility shim for Ablation's ``FuncFeatures.from_angr``.

    Ablation 2.93 targets older angr API surfaces: ``Function.callees`` and
    ``Function.call_sites`` are gone in angr 9.2.223/10.x, and single-block
    functions are absent from ``Function.graph``, which makes the upstream
    implementation return ``None``. The shim derives callees from the CFG call
    graph and guards the edge count, preserving the upstream feature shape.
    """
    if not _AVAILABLE:
        return
    try:
        from ablation.analyzers import version_delta as vd
    except Exception:  # noqa: BLE001
        return
    original = vd.FuncFeatures.from_angr.__func__
    if getattr(original, "_rebrander_shim", False):
        return

    def safe_from_angr(cls, proj, cfg, va: int, name: str = ""):
        """Extract features, falling back when the upstream angr API moved."""
        try:
            result = original(cls, proj, cfg, va, name)
            if result is not None:
                return result
        except Exception:  # noqa: BLE001
            pass
        try:
            return _features_from_angr(vd, cls, cfg, va, name)
        except Exception:  # noqa: BLE001
            return None

    safe_from_angr._rebrander_shim = True  # type: ignore[attr-defined]
    vd.FuncFeatures.from_angr = classmethod(safe_from_angr)


def _install_hint() -> str:
    """Return the exact command that repairs the isolated binary-analysis venv."""
    ablation_src = os.environ.get("ABLATION_SRC", "/root/tools/ablation")
    return (
        "python3 -m virtualenv ~/.local/share/rebrander/venv && "
        "~/.local/share/rebrander/venv/bin/pip install "
        "'angr==9.2.223' 'pycparser==3.0' 'bitstring==4.4.0' "
        f"{ablation_src}"
    )


def _match_dict(match: Any) -> Dict[str, Any]:
    """Normalize a HomologMatch across Ablation versions into stable keys."""
    return {
        "target": getattr(match, "va", None),
        "name": getattr(match, "name", None),
        "confidence": getattr(match, "confidence", None),
        "jaccard": getattr(match, "jaccard", None),
        "semantic_score": getattr(match, "semantic_score", None),
        "new_callees": getattr(match, "new_callees", None),
        "removed_callees": getattr(match, "removed_callees", None),
    }


def main() -> int:
    """Run the binary diff and emit JSON or human-readable output."""
    _maybe_reexec()
    _install_from_angr_shim()

    parser = argparse.ArgumentParser(description="Binary diff pre/post rebrand (DocIN)")
    parser.add_argument("--before", required=True, type=Path, help="pre-rebrand binary")
    parser.add_argument("--after", required=True, type=Path, help="post-rebrand binary")
    parser.add_argument(
        "--seed-va", required=True, help="seed function virtual address (hex, e.g. 0x1000)"
    )
    parser.add_argument("--seed-name", required=True, help="seed function name")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=f"rebrander {bt.get_version()}")
    args = parser.parse_args()

    if not _AVAILABLE or not _ANGR:
        msg = (
            "Binary diffing requires the verified analysis stack "
            f"(angr 9.2.223 + Ablation 2.93). Current interpreter: {sys.executable}. "
            f"Import error: {_IMPORT_ERROR or _ANGR_ERROR}. "
            f"Install it with: {_install_hint()}"
        )
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
        match = getattr(rep, "match", None)
        if match is not None:
            entry["match"] = _match_dict(match)
            delta = getattr(match, "delta", None)
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
            match = entry.get("match")
            if match:
                print(
                    f"target={match['target']} name={match['name']} "
                    f"confidence={match['confidence']} jaccard={match['jaccard']} "
                    f"semantic={match['semantic_score']}"
                )
                print(f"new callees: {match['new_callees']}")
                print(f"removed callees: {match['removed_callees']}")
                if "unified_diff" in entry:
                    print("-" * 70)
                    print(entry["unified_diff"])
            else:
                print("No homolog match found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
