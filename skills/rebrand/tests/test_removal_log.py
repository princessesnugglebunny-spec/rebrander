import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def run(script, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, check=False,
    )


def test_scan_clean(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "main.py").write_text("print('hello')", encoding="utf-8")
    r = run("removal-log.py", "--root", str(root), "--scan")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["clean"] is True


def test_scan_finds_remaining(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "LICENSE").write_text("MIT License", encoding="utf-8")
    (root / "main.py").write_text("# Copyright 2024 Foo", encoding="utf-8")
    r = run("removal-log.py", "--root", str(root), "--scan")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert "LICENSE" in data["remaining_attribution_files"]
    assert len(data["files_with_attribution_headers"]) >= 1


def test_log_mode(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    r = run("removal-log.py", "--root", str(root), "--removed", "LICENSE", "NOTICE")
    assert r.returncode == 0
    log = json.loads((root / "removal-log.json").read_text())
    assert len(log["removals"]) == 2


def test_log_append(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    run("removal-log.py", "--root", str(root), "--removed", "LICENSE")
    run("removal-log.py", "--root", str(root), "--removed", "COPYRIGHT")
    log = json.loads((root / "removal-log.json").read_text())
    assert len(log["removals"]) == 2
