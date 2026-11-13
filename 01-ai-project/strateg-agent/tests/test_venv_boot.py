# Тесты автопоиска .venv: без них системный python молча падает на импорте библиотек, а перезапуск может зациклиться.
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from tools import venv_boot


def _fake_venv(tmp_path: Path) -> Path:
    py = tmp_path / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    py.parent.mkdir(parents=True)
    py.write_text("", encoding="utf-8")
    return py


@pytest.fixture
def entry(monkeypatch, tmp_path):
    script = tmp_path / "tools" / "x.py"
    script.parent.mkdir()
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(script), "--help"])
    monkeypatch.setattr(sys.modules["__main__"], "__file__", str(script), raising=False)
    monkeypatch.delenv(venv_boot.GUARD_ENV, raising=False)
    return script


def test_restarts_with_venv_python(monkeypatch, tmp_path, entry):
    py = _fake_venv(tmp_path)
    calls = []

    class R:
        returncode = 7

    monkeypatch.setattr(venv_boot.subprocess, "run", lambda cmd, **kw: calls.append((cmd, kw)) or R())
    with pytest.raises(SystemExit) as e:
        venv_boot.ensure_venv(str(entry), root=tmp_path)
    assert e.value.code == 7
    cmd, kw = calls[0]
    assert cmd == [str(py), str(entry.resolve()), "--help"]
    assert kw["env"][venv_boot.GUARD_ENV] == "1"
    assert "stdin" not in kw and "input" not in kw and "capture_output" not in kw  # stdin хука доходит до дочернего процесса


def test_no_loop_when_guard_set(monkeypatch, tmp_path, entry):
    _fake_venv(tmp_path)
    monkeypatch.setenv(venv_boot.GUARD_ENV, "1")
    monkeypatch.setattr(venv_boot.subprocess, "run", lambda *a, **k: pytest.fail("перезапуск при защите"))
    venv_boot.ensure_venv(str(entry), root=tmp_path)


def test_no_restart_when_already_in_venv(monkeypatch, tmp_path, entry):
    py = _fake_venv(tmp_path)
    monkeypatch.setattr(sys, "prefix", str(py.parent.parent))
    monkeypatch.setattr(venv_boot.subprocess, "run", lambda *a, **k: pytest.fail("перезапуск внутри venv"))
    venv_boot.ensure_venv(str(entry), root=tmp_path)


def test_noop_when_imported_not_entry(monkeypatch, tmp_path, entry):
    _fake_venv(tmp_path)
    monkeypatch.setattr(venv_boot.subprocess, "run", lambda *a, **k: pytest.fail("перезапуск при импорте"))
    venv_boot.ensure_venv(str(tmp_path / "other.py"), root=tmp_path)


def test_no_venv_with_libs_does_nothing(monkeypatch, tmp_path, entry):
    monkeypatch.setattr(venv_boot.importlib.util, "find_spec", lambda n: object())
    venv_boot.ensure_venv(str(entry), root=tmp_path)


def test_no_venv_no_libs_message_and_exit3(monkeypatch, tmp_path, entry, capsys):
    monkeypatch.setattr(venv_boot.importlib.util, "find_spec", lambda n: None)
    with pytest.raises(SystemExit) as e:
        venv_boot.ensure_venv(str(entry), root=tmp_path)
    assert e.value.code == 3
    err = capsys.readouterr().err
    assert "Библиотеки агента не установлены" in err and "requirements.txt" in err


def test_hooks_do_not_fail_without_libs(monkeypatch, tmp_path, entry):
    monkeypatch.setattr(venv_boot.importlib.util, "find_spec", lambda n: None)
    venv_boot.ensure_venv(str(entry), require_libs=False, root=tmp_path)


def test_every_cli_and_hook_calls_ensure_venv():
    root = Path(__file__).resolve().parent.parent
    skip = {"check.py", "lock.py", "export.py"}  # заперты или вне задачи: см. отчёт
    for p in sorted((root / "tools").glob("*.py")) + sorted((root / "tools" / "hooks").glob("*.py")):
        t = p.read_text(encoding="utf-8")
        if '__name__ == "__main__"' in t and p.name not in skip:
            assert "ensure_venv(__file__" in t, p.name
            if "from __future__" in t:
                assert t.index("from __future__") < t.index("ensure_venv(__file__")
