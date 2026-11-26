"""Tests for the file-size ceiling checker."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run_check(*args: str) -> subprocess.CompletedProcess:
    """Run check-file-size.py with the given arguments."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "check-file-size.py"), *args],
        capture_output=True,
        text=True,
    )


def test_clean_tree_passes() -> None:
    """A small text file passes the ceiling check."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "ok.py").write_text("x = 1\n", encoding="utf-8")
        result = run_check("--root", str(root), "--limit", "10")
        assert result.returncode == 0
        assert "passed" in result.stdout


def test_oversized_file_fails() -> None:
    """A file over the ceiling is reported with its line count."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "big.py").write_text("\n".join(["x = 1"] * 11) + "\n", encoding="utf-8")
        result = run_check("--root", str(root), "--limit", "10", "--json")
        data = json.loads(result.stdout)
        assert result.returncode == 1
        assert data["violations"][0]["lines"] == 11


def test_skips_binary_and_cache_dirs() -> None:
    """Binary suffixes and cache directories are ignored."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "big.py").write_text("\n".join(["x = 1"] * 20), encoding="utf-8")
        (root / "image.png").write_bytes(b"\x89PNG" + b"\n" * 20)
        result = run_check("--root", str(root), "--limit", "10")
        assert result.returncode == 0
