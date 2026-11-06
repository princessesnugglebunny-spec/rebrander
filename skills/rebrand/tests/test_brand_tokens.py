import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import brand_tokens as bt


def test_split_words_simple():
    assert bt.split_words("Old Name") == ["Old", "Name"]


def test_split_words_camel():
    assert bt.split_words("OldName") == ["Old", "Name"]


def test_split_words_snake():
    assert bt.split_words("old_name") == ["old", "name"]


def test_style_pascal():
    assert bt.style(["old", "name"], "pascal") == "OldName"


def test_style_snake():
    assert bt.style(["Old", "Name"], "snake") == "old_name"


def test_variant_forms_includes_raw():
    forms = bt.variant_forms("Old Name")
    assert "Old Name" in forms
    assert "old_name" in forms
    assert "OldName" in forms
    assert "old-name" in forms


def test_token_pairs_sorted_by_length():
    brand = {
        "original": {"name": "Old Name", "slug": "old-name"},
        "target": {"name": "New Name", "slug": "new-name"},
    }
    pairs = bt.token_pairs(brand)
    assert len(pairs) > 0
    # Longer old variants first.
    lengths = [len(p[0]) for p in pairs]
    assert lengths == sorted(lengths, reverse=True)


def test_token_pairs_skips_missing_keys():
    brand = {"original": {"name": "X"}, "target": {"slug": "y"}}
    assert bt.token_pairs(brand) == []


def test_token_pairs_skips_identical():
    brand = {"original": {"name": "Same"}, "target": {"name": "Same"}}
    assert bt.token_pairs(brand) == []


def test_boundary_pattern():
    pat = bt.boundary_pattern("OldName")
    import re
    assert re.search(pat, "my OldName here")
    assert not re.search(pat, "myOldNameX")


def test_load_brand_valid(tmp_path):
    p = tmp_path / "b.json"
    p.write_text('{"original":{"name":"A","slug":"a"},"target":{"name":"B","slug":"b"}}')
    data = bt.load_brand(p)
    assert data["target"]["name"] == "B"


def test_load_brand_missing_target(tmp_path):
    p = tmp_path / "b.json"
    p.write_text('{"original":{"name":"A","slug":"a"}}')
    with pytest.raises(ValueError, match="target"):
        bt.load_brand(p)


def test_residual_variants():
    vs = bt.residual_variants(["Old Name"])
    assert "old name" in vs
    assert "old_name" in vs
