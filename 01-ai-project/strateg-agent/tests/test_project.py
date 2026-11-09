# Тесты проектов: шаблон копируется, CURRENT пишется, CLI не падает на ascii-консоли (Windows cp1251).
import os
import subprocess
import sys

from tools import common, project

ROOT = common.ROOT


def test_project_new_copies_template_sets_current(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path))
    assert project.main(["new", "demo"]) == 0
    assert (tmp_path / "CURRENT").read_text(encoding="utf-8").strip() == "demo"
    for name in ["brief.md", "questions.md", "sources.yaml", "claims.jsonl", "product.yaml", "options.md",
                 "critique.md", "strategy.md", "decisions.yaml", "state.yaml", "log.jsonl",
                 "materials/.gitkeep", "calc/.gitkeep"]:
        assert (tmp_path / "demo" / name).exists(), name
    assert common.project_path() == tmp_path / "demo"


def test_project_use_and_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path))
    project.main(["new", "a"])
    project.main(["new", "b"])
    project.main(["use", "a"])
    capsys.readouterr()
    project.main(["list"])
    out = capsys.readouterr().out
    assert "* a" in out and "  b" in out


def test_cli_survives_ascii_console(tmp_path):
    env = {**os.environ, "PYTHONIOENCODING": "ascii", "STRATEG_PROJECTS_DIR": str(tmp_path)}
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "project.py"), "list"],
                       env=env, capture_output=True, cwd=tmp_path)
    assert r.returncode == 0
    assert b"UnicodeEncodeError" not in r.stderr
