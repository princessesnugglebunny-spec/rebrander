import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def run(script, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, check=False,
    )


def test_generates_three_svgs(tmp_path, brand_json):
    root = tmp_path / "proj"
    root.mkdir()
    r = run("gen-assets.py", "--brand", str(brand_json), "--root", str(root),
            "--assets-dir", "assets", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert len(data["created"]) == 3
    assets = root / "assets"
    assert (assets / "wordmark.svg").exists()
    assert (assets / "favicon.svg").exists()
    assert (assets / "logo.svg").exists()


def test_svg_contains_brand_name(tmp_path, brand_json):
    root = tmp_path / "proj"
    root.mkdir()
    run("gen-assets.py", "--brand", str(brand_json), "--root", str(root),
        "--assets-dir", "assets")
    svg = (root / "assets" / "wordmark.svg").read_text()
    assert "New Name" in svg


def test_swap_colors(tmp_path):
    brand = tmp_path / "b.json"
    brand.write_text(json.dumps({
        "original": {"name": "O", "slug": "o", "colors": {"primary": "#ff0000"}},
        "target": {"name": "N", "slug": "n", "colors": {"primary": "#00ff00"}},
    }))
    root = tmp_path / "proj"
    root.mkdir()
    (root / "theme.css").write_text("body { color: #ff0000; }", encoding="utf-8")
    r = run("gen-assets.py", "--brand", str(brand), "--root", str(root),
            "--swap-colors")
    assert r.returncode == 0
    assert "#00ff00" in (root / "theme.css").read_text()
