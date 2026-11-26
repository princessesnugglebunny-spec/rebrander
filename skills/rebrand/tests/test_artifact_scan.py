import json
import subprocess
import sys
from pathlib import Path

from helpers import make_fixture_repo, write_brand_json


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


def test_finds_text_hits(tmp_path):
    """Test finds text hits."""
    fixture_repo = make_fixture_repo(tmp_path)
    r = run(
        "artifact-scan.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--artifacts",
        str(fixture_repo / "dist"),
        "--json",
    )
    assert r.returncode == 1  # hits found
    data = json.loads(r.stdout)
    assert data["files_with_hits"] >= 1
    files = [s["file"] for s in data["scan_results"]]
    assert "bundle.min.js" in files


def test_finds_binary_hits(tmp_path):
    """Test finds binary hits."""
    fixture_repo = make_fixture_repo(tmp_path)
    r = run(
        "artifact-scan.py",
        "--brand",
        str(fixture_repo / "brand.json"),
        "--artifacts",
        str(fixture_repo / "dist"),
        "--json",
    )
    data = json.loads(r.stdout)
    files = [s["file"] for s in data["scan_results"]]
    assert "app.bin" in files


def test_clean_artifacts(tmp_path):
    """Test clean artifacts."""
    brand_json = write_brand_json(tmp_path)
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    (clean_dir / "ok.txt").write_text("nothing here", encoding="utf-8")
    r = run("artifact-scan.py", "--brand", str(brand_json), "--artifacts", str(clean_dir), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["files_with_hits"] == 0


def test_token_flag(tmp_path):
    """Test token flag."""
    d = tmp_path / "art"
    d.mkdir()
    (d / "f.txt").write_text("hello FooBar world", encoding="utf-8")
    r = run("artifact-scan.py", "--token", "FooBar", "--artifacts", str(d), "--json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["files_with_hits"] == 1


def test_no_hits_exit_zero(tmp_path):
    """Test no hits exit zero."""
    d = tmp_path / "art"
    d.mkdir()
    (d / "f.txt").write_text("clean content", encoding="utf-8")
    r = run("artifact-scan.py", "--token", "ZZZZNOTFOUND", "--artifacts", str(d))
    assert r.returncode == 0
