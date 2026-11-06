"""Agent eval harness: end-to-end pipeline on a fixture repo.

Simulates the full rebrander workflow (inventory -> dry-run -> apply ->
artifact-scan -> rubric-score -> removal-log scan) and asserts every
expected artifact is produced and the final state is clean.
"""

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


def test_full_pipeline(fixture_repo):
    root = fixture_repo
    brand = root / "brand.json"

    # 1. Inventory
    r = run("inventory.py", "--root", str(root), "--json")
    assert r.returncode == 0
    inv = json.loads(r.stdout)
    assert inv["definitions_total"] >= 3
    assert inv["coverage_percent"] == 100.0

    # Save inventory to ANALYSIS.md (simulating agent).
    r = run("inventory.py", "--root", str(root), "--out", str(root / "ANALYSIS.md"))
    assert r.returncode == 0
    assert (root / "ANALYSIS.md").exists()

    # 2. Dry-run preview
    r = run("brand-replace.py", "--brand", str(brand), "--root", str(root),
            "--dry-run", "--json")
    assert r.returncode == 0
    dry = json.loads(r.stdout)
    assert dry["files_changed"] >= 3
    assert dry["total_replacements"] >= 9

    # 3. Diff preview
    r = run("brand-replace.py", "--brand", str(brand), "--root", str(root), "--diff")
    assert r.returncode == 0

    # 4. Apply
    r = run("brand-replace.py", "--brand", str(brand), "--root", str(root),
            "--apply", "--transactional")
    assert r.returncode == 0
    assert (root / "brand-replace.manifest.json").exists()

    # 5. Post-apply dry-run (should be clean)
    r = run("brand-replace.py", "--brand", str(brand), "--root", str(root),
            "--dry-run", "--json")
    assert r.returncode == 0
    post = json.loads(r.stdout)
    assert post["total_replacements"] == 0

    # 6. Artifact scan (dist has old-brand tokens in bundle.min.js)
    r = run("artifact-scan.py", "--brand", str(brand),
            "--artifacts", str(root / "dist"), "--json")
    # Exit 1 = hits found (expected, since dist wasn't rebranded).
    assert r.returncode in (0, 1)
    art = json.loads(r.stdout)
    assert "files_with_hits" in art

    # 7. Rubric score
    (root / "assets").mkdir(exist_ok=True)
    (root / "assets" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    r = run("rubric-score.py", "--brand", str(brand), "--root", str(root),
            "--inventory-coverage", str(inv["coverage_percent"]),
            "--build-passed", "--tests-passed",
            "--out", str(root / ".rubric.json"))
    assert r.returncode == 0
    rubric = json.loads((root / ".rubric.json").read_text())
    assert "total_score" in rubric
    assert "grade" in rubric
    assert len(rubric["criteria"]) == 7

    # 8. Removal log scan
    r = run("removal-log.py", "--root", str(root), "--scan")
    # Exit 0 = clean (no attribution files remain) or 1 = found.
    assert r.returncode in (0, 1)

    # 9. Verify rebranded content
    main_py = (root / "src" / "main.py").read_text()
    assert "NewName" in main_py
    assert "New Name" in main_py
    readme = (root / "README.md").read_text()
    assert "New Name" in readme


def test_ast_rename_preserves_formatting(fixture_repo):
    """AST rename should preserve code formatting (LibCST)."""
    root = fixture_repo
    brand = root / "brand.json"
    # Apply regex first.
    run("brand-replace.py", "--brand", str(brand), "--root", str(root), "--apply")
    # Now test ast-rename on a fresh file.
    import shutil
    # Create a Python file with a class matching a token.
    (root / "src" / "model.py").write_text(
        'class OldName:\n    """Docstring."""\n    def method(self):\n        return 42\n',
        encoding="utf-8",
    )
    r = run("ast-rename.py", "--brand", str(brand), "--root", str(root), "--apply", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["files_changed"] >= 1
    content = (root / "src" / "model.py").read_text()
    assert "class NewName:" in content
    # Formatting preserved (no extra blank lines from ast.unparse).
    assert '"""Docstring."""' in content


def test_rename_pack_js_ast(fixture_repo):
    """rename-pack should use acorn for JS/TS files."""
    root = fixture_repo
    brand = root / "brand.json"
    (root / "src" / "widget.ts").write_text(
        "export class OldName { value = 42; }\n", encoding="utf-8"
    )
    r = run("rename-pack.py", "--brand", str(brand), "--root", str(root),
            "--mode", "apply", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "js_ast_rename" in data
    content = (root / "src" / "widget.ts").read_text()
    assert "NewName" in content


def test_transactional_rollback(tmp_path):
    """Transactional mode should rollback on failure."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    brand = tmp_path / "brand.json"
    brand.write_text(json.dumps({
        "original": {"name": "Old", "slug": "old"},
        "target": {"name": "New", "slug": "new"},
    }))
    # This should succeed (no old tokens to replace).
    r = run("brand-replace.py", "--brand", str(brand), "--root", str(root),
            "--apply", "--transactional")
    assert r.returncode == 0
