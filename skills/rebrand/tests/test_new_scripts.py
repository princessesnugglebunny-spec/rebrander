"""Smoke tests for newer scripts."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True)


def test_doctor(tmp_path):
    r = run("doctor.py", "--json")
    assert r.returncode in (0, 1)
    data = json.loads(r.stdout)
    assert "checks" in data


def test_coupling_review(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    (root / "a.py").write_text("x = os.environ['FOO']\n", encoding="utf-8")
    r = run("coupling-review.py", "--root", str(root), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["total"] >= 1


def test_differentiate(tmp_path):
    brand = tmp_path / "brand.json"
    brand.write_text(json.dumps({"original": {"name": "Old", "slug": "old"}, "target": {"name": "New", "slug": "new"}}))
    root = tmp_path / "r"
    root.mkdir()
    r = run("differentiate.py", "--brand", str(brand), "--root", str(root))
    assert r.returncode == 0
    assert (root / "DESIGN.md").exists()


def test_toggle(tmp_path):
    brand = tmp_path / "brand.json"
    brand.write_text(json.dumps({"original": {"name": "Old", "slug": "old"}, "target": {"name": "New", "slug": "new"}}))
    r = run("toggle.py", "--brand", str(brand), "--feature", "x", "--enable")
    assert r.returncode == 0
    data = json.loads(brand.read_text())
    assert data["features"]["x"] is True


def test_capture_compare(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    (root / "a.txt").write_text("hi", encoding="utf-8")
    cap1 = tmp_path / "c1.json"
    cap2 = tmp_path / "c2.json"
    r1 = run("capture.py", "--scenario", "s1", "--command", "echo hi", "--root", str(root), "--out", str(cap1))
    assert r1.returncode == 0
    (root / "a.txt").write_text("bye", encoding="utf-8")
    r2 = run("capture.py", "--scenario", "s2", "--command", "echo hi", "--root", str(root), "--out", str(cap2))
    assert r2.returncode == 0
    r3 = run("compare-captures.py", "--reference", str(cap1), "--candidate", str(cap2), "--json")
    assert r3.returncode in (0, 1)
    data = json.loads(r3.stdout)
    assert "coverage" in data


def test_verify_browser_skip_or_run(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    brand = tmp_path / "brand.json"
    brand.write_text(json.dumps({"original": {"name": "Old", "slug": "old"}, "target": {"name": "New", "slug": "new"}}))
    r = run("verify-browser.py", "--url", "http://127.0.0.1:1", "--brand", str(brand), "--json")
    assert r.returncode in (0, 1)
    data = json.loads(r.stdout)
    assert isinstance(data, dict)