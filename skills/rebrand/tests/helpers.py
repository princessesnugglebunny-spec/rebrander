"""Shared test helpers for the rebrander script tests."""

import json
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def brand_data():
    """Return a minimal valid brand payload."""
    return {
        "original": {
            "name": "Old Name",
            "slug": "old-name",
            "org": "OldOrg",
            "package": "old_name",
            "namespace": "OldName",
        },
        "target": {
            "name": "New Name",
            "slug": "new-name",
            "org": "NewOrg",
            "package": "new_name",
            "namespace": "NewName",
        },
    }


def write_brand_json(path):
    """Write a minimal valid brand.json into path and return its file path."""
    target = Path(path) / "brand.json"
    target.write_text(json.dumps(brand_data()), encoding="utf-8")
    return target


def make_fixture_repo(tmp_path):
    """Create a small multi-language repo with old-brand tokens and return its root."""
    root = Path(tmp_path) / "repo"
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
    (root / "README.md").write_text(
        "# Old Name\n\nSee https://old-name.example.com\n", encoding="utf-8"
    )
    write_brand_json(root)
    (root / "dist").mkdir()
    (root / "dist" / "bundle.min.js").write_text('var x="OldName";', encoding="utf-8")
    (root / "dist" / "app.bin").write_bytes(b"Old Name\x00binary")
    return root
