"""Minimal MCP stdio server exposing rebrander tools (SRP: serving only)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import brand_tokens as bt  # noqa: E402

TOOLS = [
    {"name": "rebrand_doctor", "description": "Check environment", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "rebrand_source_scan", "description": "Scan for leftover brand tokens", "inputSchema": {"type": "object", "properties": {"root": {"type": "string"}, "brand": {"type": "string"}}}},
]


def handle(req):
    """Handle one JSON-RPC request and return a response dict."""
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "rebrander", "version": bt.get_version()}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        if name == "rebrand_doctor":
            r = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py"), "--json"], capture_output=True, text=True)
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": r.stdout or r.stderr}]}}
        if name == "rebrand_source_scan":
            cmd = [sys.executable, str(SCRIPTS / "source-scan.py"), "--root", args["root"], "--json"]
            if args.get("brand"):
                cmd += ["--brand", args["brand"]]
            r = subprocess.run(cmd, capture_output=True, text=True)
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": r.stdout or r.stderr}]}}
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "unknown tool"}}
    if method == "notifications/initialized":
        return None
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}


def main() -> int:
    """Run the stdio loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
