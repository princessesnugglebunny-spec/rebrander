"""Tests for derive-checks.py."""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def test_derives_cases(tmp_path):
    plan = tmp_path / "PLAN.md"
    plan.write_text("## 8. Acceptance cases\n- [ ] CLI starts\n- [ ] Tests pass\n", encoding="utf-8")
    out = tmp_path / "checks.py"
    r = subprocess.run([sys.executable, str(SCRIPTS / "derive-checks.py"), "--plan", str(plan), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0
    text = out.read_text()
    assert "test_cli_starts" in text
    assert "test_tests_pass" in text
    assert "ail-derived-from" in text