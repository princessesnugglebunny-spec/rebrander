import json
import subprocess
import sys
from pathlib import Path

from helpers import make_fixture_repo


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


def test_extracts_python(tmp_path):
    """Test extracts python."""
    fixture_repo = make_fixture_repo(tmp_path)
    r = run("inventory.py", "--root", str(fixture_repo), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    names = [d["name"] for d in data["definitions"]]
    assert "OldName" in names
    assert "old_function" in names


def test_extracts_js(tmp_path):
    """Test extracts js."""
    fixture_repo = make_fixture_repo(tmp_path)
    r = run("inventory.py", "--root", str(fixture_repo), "--json")
    data = json.loads(r.stdout)
    names = [d["name"] for d in data["definitions"]]
    assert "oldFunction" in names


def test_coverage_100(tmp_path):
    """Test coverage 100."""
    fixture_repo = make_fixture_repo(tmp_path)
    r = run("inventory.py", "--root", str(fixture_repo), "--json")
    data = json.loads(r.stdout)
    assert data["coverage_percent"] == 100.0


def test_skips_unsupported(tmp_path):
    """Test skips unsupported."""
    (tmp_path / "data.csv").write_text("a,b,c")
    (tmp_path / "readme.txt").write_text("hello")
    r = run("inventory.py", "--root", str(tmp_path), "--json")
    data = json.loads(r.stdout)
    assert data["files_scanned"] == 0
    assert data["definitions_total"] == 0


def test_markdown_output(tmp_path):
    """Test markdown output."""
    fixture_repo = make_fixture_repo(tmp_path)
    r = run("inventory.py", "--root", str(fixture_repo))
    assert "| Name | Kind | Location | Signature |" in r.stdout
    assert "OldName" in r.stdout


def test_extracts_go(tmp_path):
    """Test extracts go."""
    (tmp_path / "main.go").write_text(
        "package main\n\nfunc Hello() {}\ntype Foo struct {}\n",
        encoding="utf-8",
    )
    r = run("inventory.py", "--root", str(tmp_path), "--json")
    data = json.loads(r.stdout)
    names = [d["name"] for d in data["definitions"]]
    assert "Hello" in names
    assert "Foo" in names


def test_extracts_rust(tmp_path):
    """Test extracts rust."""
    (tmp_path / "main.rs").write_text(
        "pub fn hello() {}\npub struct Foo {}\npub enum Bar {}\n",
        encoding="utf-8",
    )
    r = run("inventory.py", "--root", str(tmp_path), "--json")
    data = json.loads(r.stdout)
    names = [d["name"] for d in data["definitions"]]
    assert "hello" in names
    assert "Foo" in names
    assert "Bar" in names


def test_extracts_java(tmp_path):
    """Test extracts java."""
    (tmp_path / "Main.java").write_text(
        "public class Foo {}\npublic interface Bar {}\n",
        encoding="utf-8",
    )
    r = run("inventory.py", "--root", str(tmp_path), "--json")
    data = json.loads(r.stdout)
    names = [d["name"] for d in data["definitions"]]
    assert "Foo" in names
    assert "Bar" in names


def test_extracts_csharp(tmp_path):
    """Test extracts csharp."""
    (tmp_path / "Main.cs").write_text(
        "public class Foo {}\npublic interface IBar {}\n",
        encoding="utf-8",
    )
    r = run("inventory.py", "--root", str(tmp_path), "--json")
    data = json.loads(r.stdout)
    names = [d["name"] for d in data["definitions"]]
    assert "Foo" in names
    assert "IBar" in names
