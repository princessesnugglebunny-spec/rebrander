"""Tests for cache.py."""

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import cache as c


def test_round_trip():
    c.invalidate("ns", "payload")
    c.set("ns", "payload", {"a": 1})
    assert c.get("ns", "payload") == {"a": 1}


def test_miss():
    assert c.get("ns2", "nope") is None