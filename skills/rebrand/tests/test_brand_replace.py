import json
import subprocess
import sys
from pathlib import Path

from helpers import make_fixture_repo


SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def run(script, *args):
    """Run a script and return the completed process."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_dry_run_counts(tmp_path):
    """Test dry run counts."""
    fixture_repo = make_fixture_repo(tmp_path)
    r = run(
        "brand-replace.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--root",
        str(fixture_repo),
        "--dry-run",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["files_changed"] >= 3
    assert data["total_replacements"] >= 9


def test_brand_json_not_self_modified(tmp_path):
    """Test brand json not self modified."""
    fixture_repo = make_fixture_repo(tmp_path)
    original_brand = (fixture_repo / "brand.json").read_text()
    run(
        "brand-replace.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--root",
        str(fixture_repo),
        "--apply",
    )
    assert (fixture_repo / "brand.json").read_text() == original_brand


def test_apply_changes_files(tmp_path):
    """Test apply changes files."""
    fixture_repo = make_fixture_repo(tmp_path)
    run(
        "brand-replace.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--root",
        str(fixture_repo),
        "--apply",
    )
    main_py = (fixture_repo / "src" / "main.py").read_text()
    assert "NewName" in main_py
    assert "New Name" in main_py
    assert "OLD_NAME_CONST" not in main_py  # replaced by NEW_NAME_CONST
    readme = (fixture_repo / "README.md").read_text()
    assert "New Name" in readme
    assert "new-name.example.com" in readme


def test_idempotent(tmp_path):
    """Test idempotent."""
    fixture_repo = make_fixture_repo(tmp_path)
    run(
        "brand-replace.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--root",
        str(fixture_repo),
        "--apply",
    )
    r = run(
        "brand-replace.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--root",
        str(fixture_repo),
        "--dry-run",
        "--json",
    )
    data = json.loads(r.stdout)
    assert data["total_replacements"] == 0
    assert data["files_changed"] == 0


def test_manifest_written(tmp_path):
    """Test manifest written."""
    fixture_repo = make_fixture_repo(tmp_path)
    run(
        "brand-replace.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--root",
        str(fixture_repo),
        "--apply",
    )
    manifest = fixture_repo / "brand-replace.manifest.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    assert "touched" in data
    assert len(data["touched"]) >= 3


def test_atomic_no_tmp_leftover(tmp_path):
    """Test atomic no tmp leftover."""
    fixture_repo = make_fixture_repo(tmp_path)
    run(
        "brand-replace.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--root",
        str(fixture_repo),
        "--apply",
    )
    tmps = list(fixture_repo.rglob("*.brandtmp"))
    assert tmps == []


def test_binary_files_skipped(tmp_path):
    """Test binary files skipped."""
    fixture_repo = make_fixture_repo(tmp_path)
    # dist/bundle.min.js is text, dist/app.bin is binary.
    # The binary should not be modified.
    original_bin = (fixture_repo / "dist" / "app.bin").read_bytes()
    run(
        "brand-replace.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--root",
        str(fixture_repo),
        "--apply",
    )
    assert (fixture_repo / "dist" / "app.bin").read_bytes() == original_bin


def test_diff_mode_no_write(tmp_path):
    """Test diff mode no write."""
    fixture_repo = make_fixture_repo(tmp_path)
    before = (fixture_repo / "src" / "main.py").read_text()
    run(
        "brand-replace.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--root",
        str(fixture_repo),
        "--diff",
    )
    after = (fixture_repo / "src" / "main.py").read_text()
    assert before == after  # diff doesn't write


def test_diff_out_writes_file_without_touching_source(tmp_path):
    """Test diff out writes file without touching source."""
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "main.py"
    source.write_text("print('Old')\n", encoding="utf-8")
    brand = tmp_path / "brand.json"
    brand.write_text(
        json.dumps(
            {
                "original": {"name": "Old", "slug": "old"},
                "target": {"name": "New", "slug": "new"},
            }
        )
    )
    diff_path = tmp_path / "changes.diff"
    result = run(
        "brand-replace.py",
        "--brand",
        str(brand),
        "--root",
        str(root),
        "--diff",
        "--diff-out",
        str(diff_path),
    )
    assert result.returncode == 0
    diff = diff_path.read_text()
    assert "-print('Old')" in diff
    assert "+print('New')" in diff
    assert source.read_text() == "print('Old')\n"


def test_transactional_rollback_restores_earlier_files(tmp_path):
    """Test transactional rollback restores earlier files."""
    root = tmp_path / "repo"
    root.mkdir()
    first = root / "a.py"
    first.write_text("value = 'Old'\n", encoding="utf-8")
    second = root / "b.py"
    second.write_text("value = 'Old'\n", encoding="utf-8")
    (root / "b.py.brandtmp").mkdir()
    brand = tmp_path / "brand.json"
    brand.write_text(
        json.dumps(
            {
                "original": {"name": "Old", "slug": "old"},
                "target": {"name": "New", "slug": "new"},
            }
        )
    )
    result = run(
        "brand-replace.py",
        "--brand",
        str(brand),
        "--root",
        str(root),
        "--apply",
        "--transactional",
    )
    assert result.returncode == 1
    assert "ERROR writing" in result.stderr
    assert first.read_text() == "value = 'Old'\n"
    assert second.read_text() == "value = 'Old'\n"
    assert not (root / "a.py.brandtmp").exists()


def test_schema_validation_rejects_bad_brand(tmp_path):
    """Test schema validation rejects bad brand."""
    bad = tmp_path / "bad.json"
    bad.write_text('{"original": {"slug": "x"}, "target": {"name": "Y", "slug": "y"}}')
    r = run("brand-replace.py", "--brand", str(bad), "--root", str(tmp_path), "--dry-run")
    assert r.returncode != 0
