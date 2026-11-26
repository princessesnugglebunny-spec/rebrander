"""Tests for adopt.py."""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def test_adopt_copies_missing(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hi", encoding="utf-8")
    dst = tmp_path / "dst"
    dst.mkdir()
    r = subprocess.run([sys.executable, str(SCRIPTS / "adopt.py"), "--source", str(src), "--target", str(dst)], capture_output=True, text=True)
    assert r.returncode == 0
    assert (dst / "a.txt").read_text() == "hi"