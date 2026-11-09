# Тесты rules.lock: без них правку правил или проверяющего никто не заметит на старте сессии.
from pathlib import Path

import pytest

from tools import check, lock
from tools.common import read_jsonl, read_yaml


@pytest.fixture
def tmp_root(tmp_path):
    root = tmp_path / "agent"
    (root / "rules").mkdir(parents=True)
    (root / "prompts").mkdir()
    (root / "tools").mkdir()
    (root / "rules" / "a.md").write_text("правило\n", encoding="utf-8")
    (root / "prompts" / "p.md").write_text("промпт\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("агент\n", encoding="utf-8")
    (root / "tools" / "check.py").write_text("# check\n", encoding="utf-8")
    (root / "tools" / "lock.py").write_text("# lock\n", encoding="utf-8")
    (root / "tools" / "other.py").write_text("# не запирается\n", encoding="utf-8")
    lock.update(root, "старт")
    return root


def test_lock_compute_scope(tmp_root):
    files = lock.compute(tmp_root)
    assert set(files) == {"rules/a.md", "prompts/p.md", "AGENTS.md", "tools/check.py", "tools/lock.py"}


def test_lock_verify_detects_change(tmp_root):
    assert lock.verify(tmp_root) == []
    (tmp_root / "rules" / "a.md").write_text("подменили\n", encoding="utf-8")
    (tmp_root / "rules" / "new.md").write_text("новое\n", encoding="utf-8")
    (tmp_root / "prompts" / "p.md").unlink()
    (tmp_root / "tools" / "other.py").write_text("# правка вне lock\n", encoding="utf-8")
    problems = lock.verify(tmp_root)
    assert any("rules/a.md" in p for p in problems)
    assert any("rules/new.md" in p for p in problems)
    assert any("prompts/p.md" in p for p in problems)
    assert not any("other.py" in p for p in problems)


def test_lock_ignores_line_endings(tmp_root):
    (tmp_root / "AGENTS.md").write_bytes("агент\r\n".encode("utf-8"))
    assert lock.verify(tmp_root) == []


def test_lock_update_writes_history_with_reason(tmp_root):
    (tmp_root / "rules" / "a.md").write_text("v2\n", encoding="utf-8")
    lock.update(tmp_root, "правка правила")
    data = read_yaml(tmp_root / "rules.lock")
    last = data["history"][-1]
    assert last["reason"] == "правка правила"
    assert last["changed"] == ["rules/a.md"]
    assert last["updated_at"]
    assert len(data["history"]) == 2
    assert lock.verify(tmp_root) == []


def test_lock_update_logs_event_in_project(tmp_root, tmp_project):
    (Path(__import__("os").environ["STRATEG_PROJECTS_DIR"]) / "CURRENT").write_text(tmp_project, encoding="utf-8")
    lock.update(tmp_root, "причина")
    events = [e for e in read_jsonl(Path(__import__("os").environ["STRATEG_PROJECTS_DIR"]) / tmp_project / "log.jsonl")
              if e["kind"] == "lock_update"]
    assert events and events[0]["reason"] == "причина"


def test_lock_update_requires_reason(tmp_root):
    with pytest.raises(ValueError):
        lock.update(tmp_root, "  ")


def test_lock_cli_exit_codes(tmp_root, capsys):
    assert lock.main(["--root", str(tmp_root), "--verify"]) == 0
    (tmp_root / "AGENTS.md").write_text("взлом\n", encoding="utf-8")
    assert lock.main(["--root", str(tmp_root), "--verify"]) == 1
    assert "AGENTS.md" in capsys.readouterr().out


def test_check11_fails_on_lock_mismatch(tmp_root):
    assert [f.level for f in check.check_lock(tmp_root)] == ["OK"]
    (tmp_root / "rules" / "a.md").write_text("подмена\n", encoding="utf-8")
    fs = check.check_lock(tmp_root)
    assert fs[0].level == "FAIL" and fs[0].check == 11 and "rules/a.md" in fs[0].msg

