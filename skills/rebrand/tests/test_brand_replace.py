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


def test_dry_run_counts(fixture_repo, brand_json):
    r = run("brand-replace.py", "--brand", str(fixture_repo / "brand.json"),
            "--root", str(fixture_repo), "--dry-run", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["files_changed"] >= 3
    assert data["total_replacements"] >= 9


def test_brand_json_not_self_modified(fixture_repo):
    original_brand = (fixture_repo / "brand.json").read_text()
    run("brand-replace.py", "--brand", str(fixture_repo / "brand.json"),
        "--root", str(fixture_repo), "--apply")
    assert (fixture_repo / "brand.json").read_text() == original_brand


def test_apply_changes_files(fixture_repo):
    run("brand-replace.py", "--brand", str(fixture_repo / "brand.json"),
        "--root", str(fixture_repo), "--apply")
    main_py = (fixture_repo / "src" / "main.py").read_text()
    assert "NewName" in main_py
    assert "New Name" in main_py
    assert "OLD_NAME_CONST" not in main_py  # replaced by NEW_NAME_CONST
    readme = (fixture_repo / "README.md").read_text()
    assert "New Name" in readme
    assert "new-name.example.com" in readme


def test_idempotent(fixture_repo):
    run("brand-replace.py", "--brand", str(fixture_repo / "brand.json"),
        "--root", str(fixture_repo), "--apply")
    r = run("brand-replace.py", "--brand", str(fixture_repo / "brand.json"),
            "--root", str(fixture_repo), "--dry-run", "--json")
    data = json.loads(r.stdout)
    assert data["total_replacements"] == 0
    assert data["files_changed"] == 0


def test_manifest_written(fixture_repo):
    run("brand-replace.py", "--brand", str(fixture_repo / "brand.json"),
        "--root", str(fixture_repo), "--apply")
    manifest = fixture_repo / "brand-replace.manifest.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    assert "touched" in data
    assert len(data["touched"]) >= 3


def test_atomic_no_tmp_leftover(fixture_repo):
    run("brand-replace.py", "--brand", str(fixture_repo / "brand.json"),
        "--root", str(fixture_repo), "--apply")
    tmps = list(fixture_repo.rglob("*.brandtmp"))
    assert tmps == []


def test_binary_files_skipped(fixture_repo):
    # dist/bundle.min.js is text, dist/app.bin is binary.
    # The binary should not be modified.
    original_bin = (fixture_repo / "dist" / "app.bin").read_bytes()
    run("brand-replace.py", "--brand", str(fixture_repo / "brand.json"),
        "--root", str(fixture_repo), "--apply")
    assert (fixture_repo / "dist" / "app.bin").read_bytes() == original_bin


def test_diff_mode_no_write(fixture_repo):
    before = (fixture_repo / "src" / "main.py").read_text()
    run("brand-replace.py", "--brand", str(fixture_repo / "brand.json"),
        "--root", str(fixture_repo), "--diff")
    after = (fixture_repo / "src" / "main.py").read_text()
    assert before == after  # diff doesn't write


def test_schema_validation_rejects_bad_brand(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"original": {"slug": "x"}, "target": {"name": "Y", "slug": "y"}}')
    r = run("brand-replace.py", "--brand", str(bad), "--root", str(tmp_path), "--dry-run")
    assert r.returncode != 0
