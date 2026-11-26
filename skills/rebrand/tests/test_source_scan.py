"""Tests for source-scan.py."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "source-scan.py"), *args], capture_output=True, text=True)


def test_clean_tree_zero_hits(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    brand = tmp_path / "brand.json"
    brand.write_text(json.dumps({"original": {"name": "Old", "slug": "old"}, "target": {"name": "New", "slug": "new"}}))
    r = run("--root", str(root), "--brand", str(brand), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["brand_hits"] == []


def test_dirty_tree_has_hits(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("print('Old Name')\n", encoding="utf-8")
    brand = tmp_path / "brand.json"
    brand.write_text(json.dumps({"original": {"name": "Old Name", "slug": "old-name"}, "target": {"name": "New Name", "slug": "new-name"}}))
    r = run("--root", str(root), "--brand", str(brand), "--json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert len(data["brand_hits"]) >= 1