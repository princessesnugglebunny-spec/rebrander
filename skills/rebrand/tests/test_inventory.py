import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def run(script, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, check=False,
    )


def test_extracts_python(fixture_repo):
    r = run("inventory.py", "--root", str(fixture_repo), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    names = [d["name"] for d in data["definitions"]]
    assert "OldName" in names
    assert "old_function" in names


def test_extracts_js(fixture_repo):
    r = run("inventory.py", "--root", str(fixture_repo), "--json")
    data = json.loads(r.stdout)
    names = [d["name"] for d in data["definitions"]]
    assert "oldFunction" in names


def test_coverage_100(fixture_repo):
    r = run("inventory.py", "--root", str(fixture_repo), "--json")
    data = json.loads(r.stdout)
    assert data["coverage_percent"] == 100.0


def test_skips_unsupported(tmp_path):
    (tmp_path / "data.csv").write_text("a,b,c")
    (tmp_path / "readme.txt").write_text("hello")
    r = run("inventory.py", "--root", str(tmp_path), "--json")
    data = json.loads(r.stdout)
    assert data["files_scanned"] == 0
    assert data["definitions_total"] == 0


def test_markdown_output(fixture_repo):
    r = run("inventory.py", "--root", str(fixture_repo))
    assert "| Name | Kind | Location | Signature |" in r.stdout
    assert "OldName" in r.stdout


def test_out_file(fixture_repo, tmp_path):
    out = tmp_path / "inv.md"
    r = run("inventory.py", "--root", str(fixture_repo), "--out", str(out))
    assert r.returncode == 0
    assert out.exists()
    assert "OldName" in out.read_text()
