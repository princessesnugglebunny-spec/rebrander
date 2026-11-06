"""Shared pytest fixtures for the rebrander script tests."""

import json
import shutil
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


@pytest.fixture
def scripts_dir():
    return SCRIPTS


@pytest.fixture
def brand_json(tmp_path):
    """A minimal valid brand.json."""
    data = {
        "original": {"name": "Old Name", "slug": "old-name", "org": "OldOrg",
                     "package": "old_name", "namespace": "OldName"},
        "target": {"name": "New Name", "slug": "new-name", "org": "NewOrg",
                   "package": "new_name", "namespace": "NewName"},
    }
    p = tmp_path / "brand.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def fixture_repo(tmp_path, brand_json):
    """A small multi-language repo with old-brand tokens."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text(
        '"""Old Name module."""\nclass OldName:\n    def old_function(self):\n'
        '        OLD_NAME_CONST = 1\n        return "Old Name"\n',
        encoding="utf-8",
    )
    (root / "src" / "app.js").write_text(
        'export function oldFunction() { const oldName = 5; /* old-name */ return "Old Name"; }\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Old Name\n\nSee https://old-name.example.com\n", encoding="utf-8")
    (root / "brand.json").write_text(brand_json.read_text(), encoding="utf-8")
    # binary artifact
    (root / "dist").mkdir()
    (root / "dist" / "bundle.min.js").write_text('var x="OldName";', encoding="utf-8")
    (root / "dist" / "app.bin").write_bytes(b"Old Name\x00binary")
    return root