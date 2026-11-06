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


def _make_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("class OldName: pass\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "original"], check=True)
    subprocess.run(["git", "-C", str(repo), "branch", "rebrand/original"], check=True)
    return repo


def test_not_git_repo(tmp_path):
    d = tmp_path / "notgit"
    d.mkdir()
    r = run("revert.py", "--root", str(d))
    assert r.returncode == 2


def test_list_branches(tmp_path):
    repo = _make_git_repo(tmp_path)
    r = run("revert.py", "--root", str(repo), "--list")
    assert r.returncode == 0
    assert "rebrand/original" in r.stdout


def test_full_revert(tmp_path):
    repo = _make_git_repo(tmp_path)
    # Simulate rebrand.
    (repo / "main.py").write_text("class NewName: pass\n", encoding="utf-8")
    (repo / "brand.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "rebranded"], check=True)
    r = run("revert.py", "--root", str(repo))
    assert r.returncode == 0
    assert "class OldName" in (repo / "main.py").read_text()
    assert not (repo / "brand.json").exists()


def test_per_file_revert(tmp_path):
    repo = _make_git_repo(tmp_path)
    (repo / "main.py").write_text("class NewName: pass\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "rebranded"], check=True)
    r = run("revert.py", "--root", str(repo), "--file", "main.py")
    assert r.returncode == 0
    assert "class OldName" in (repo / "main.py").read_text()
