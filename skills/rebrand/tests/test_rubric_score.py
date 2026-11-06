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


def test_score_perfect(fixture_repo):
    # Apply rebrand first so leftover scan is clean.
    import subprocess
    subprocess.run(
        [sys.executable, str(SCRIPTS / "brand-replace.py"),
         "--brand", str(fixture_repo / "brand.json"),
         "--root", str(fixture_repo), "--apply"],
        check=False,
    )
    (fixture_repo / "assets").mkdir(exist_ok=True)
    (fixture_repo / "assets" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    r = run("rubric-score.py", "--brand", str(fixture_repo / "brand.json"),
            "--root", str(fixture_repo), "--inventory-coverage", "100",
            "--build-passed", "--tests-passed", "--out",
            str(fixture_repo / ".rubric.json"))
    assert r.returncode == 0
    data = json.loads((fixture_repo / ".rubric.json").read_text())
    assert data["total_score"] >= 80
    assert data["grade"] in ("A", "B")


def test_score_degrades_without_build(fixture_repo):
    r = run("rubric-score.py", "--brand", str(fixture_repo / "brand.json"),
            "--root", str(fixture_repo), "--inventory-coverage", "100",
            "--out", str(fixture_repo / ".rubric2.json"))
    assert r.returncode == 0
    data = json.loads((fixture_repo / ".rubric2.json").read_text())
    # feature_preservation should be 0 (no build/tests)
    assert data["criteria"]["feature_preservation"]["score"] == 0


def test_score_output_has_all_criteria(fixture_repo):
    run("rubric-score.py", "--brand", str(fixture_repo / "brand.json"),
        "--root", str(fixture_repo), "--inventory-coverage", "50",
        "--out", str(fixture_repo / ".rubric3.json"))
    data = json.loads((fixture_repo / ".rubric3.json").read_text())
    expected = {"brand_completeness", "feature_preservation", "leftover_scan",
                "attribution_removal", "inventory_coverage", "documentation",
                "assets_theme"}
    assert set(data["criteria"].keys()) == expected


def test_grade_thresholds():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rs", SCRIPTS / "rubric-score.py")
    # Can't import (has main guard); test _grade via exec.
    src = (SCRIPTS / "rubric-score.py").read_text()
    ns = {"__file__": str(SCRIPTS / "rubric-score.py"), "__name__": "rs"}
    exec(compile(src, "rs", "exec"), ns)
    assert ns["_grade"](95) == "A"
    assert ns["_grade"](85) == "B"
    assert ns["_grade"](75) == "C"
    assert ns["_grade"](65) == "D"
    assert ns["_grade"](50) == "F"
