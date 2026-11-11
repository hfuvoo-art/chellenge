# Тесты состояния и журнала: проверяют, что action_id стабилен и «сделано» переживает перезапуск, иначе возобновление дублирует работу.
import re

import pytest

from tools import log, state
from tools.common import read_jsonl


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path))
    d = tmp_path / "p1"
    d.mkdir()
    (d / "state.yaml").write_text("step: {n: 0, name: not-started}\ndone: {}\n", encoding="utf-8")
    return "p1"


def test_action_id_format_and_stability():
    a = state.action_id("extract", "S-003:part-07", "текст части")
    assert re.match(r"^extract:S-003:part-07:[0-9a-f]{12}$", a)
    assert a == state.action_id("extract", "S-003:part-07", "текст части")
    assert a != state.action_id("extract", "S-003:part-07", "другой текст")


def test_mark_done_idempotent_persisted(proj):
    aid = state.action_id("extract", "S-001:part-01", "x")
    assert not state.is_done(proj, aid)
    state.mark_done(proj, aid, {"claims": 3})
    state.mark_done(proj, aid, {"claims": 99})
    assert state.is_done(proj, aid)
    st = state.load(proj)
    assert list(st["done"]) == [aid]
    assert st["done"][aid]["claims"] == 3


def test_wait_resolve_degraded_step(proj):
    state.set_step(proj, 2, "collect")
    state.wait_human(proj, "Точка 1", "Какой рынок?")
    assert state.load(proj)["waiting"]["point"] == "Точка 1"
    state.resolve_human(proj, "Точка 1", "Турция", 2)
    st = state.load(proj)
    assert st["waiting"] is None and st["human"][0]["minutes"] == 2 and st["step"]["n"] == 2
    state.add_degraded(proj, "env-model", "без ключа")
    state.add_degraded(proj, "env-model", "без ключа")
    assert len(state.load(proj)["degraded"]) == 1


def test_log_event_and_cli(proj, tmp_path):
    log.event(proj, "note", text="Привет ₽")
    assert log.main(["-p", proj, "human", "5", "ручной обход"]) == 0
    assert log.main(["-p", proj, "model", "0.5", "--manual"]) == 0
    assert log.main(["-p", proj, "search", "eSIM Турция", "--engine", "claude"]) == 0
    kinds = [e["kind"] for e in read_jsonl(tmp_path / proj / "log.jsonl")]
    assert kinds == ["note", "human", "model", "search"]


def test_cli_step_wait_resolve_show(proj, tmp_path, capsys):
    assert state.main(["-p", proj, "step", "1", "frame"]) == 0
    assert state.main(["-p", proj, "wait", "точка 1", "Подтверждаете постановку?"]) == 0
    st = state.load(proj)
    assert st["step"] == {"n": 1, "name": "frame"} and st["waiting"]["point"] == "точка 1"
    assert state.main(["-p", proj, "resolve", "Точка 1", "--summary", "ок", "--minutes", "4"]) == 0
    st = state.load(proj)
    assert st["waiting"] is None and st["human"][0]["minutes"] == 4 and st["human"][0]["summary"] == "ок"
    kinds = [e["kind"] for e in read_jsonl(tmp_path / proj / "log.jsonl")]
    assert kinds == ["step", "wait_human", "human"]
    capsys.readouterr()
    assert state.main(["-p", proj, "show"]) == 0
    out = capsys.readouterr().out
    assert "step:" in out and "Точка 1" in out


def test_cli_step_mismatch_code_3(proj, capsys):
    assert state.main(["-p", proj, "step", "2", "frame"]) == 3
    assert state.main(["-p", proj, "step", "7", "frame"]) == 3
    assert state.main(["-p", proj, "step", "1", "nonsense"]) == 3
    err = capsys.readouterr().err
    assert "Что сделать" in err and "after-decision" in err
    assert state.load(proj)["step"]["n"] == 0  # состояние не тронуто


def test_cli_resolve_requires_wait_and_same_point(proj, capsys):
    assert state.main(["-p", proj, "resolve", "точка 1", "--summary", "x", "--minutes", "1"]) == 3
    state.wait_human(proj, "точка 2", "Какой вариант?")
    assert state.main(["-p", proj, "resolve", "точка 1", "--summary", "x", "--minutes", "1"]) == 3
    assert state.load(proj)["waiting"] is not None and state.load(proj)["human"] == []
    assert state.main(["-p", proj, "resolve", "точка 2", "--summary", "O2", "--minutes", "-1"]) == 3
    assert state.main(["-p", proj, "resolve", "точка 2", "--summary", "O2", "--minutes", "3"]) == 0
    assert state.main(["-p", proj, "resolve", "точка 2", "--summary", "O2", "--minutes", "3"]) == 3  # повтор не удваивает
    assert len(state.load(proj)["human"]) == 1


def test_cli_resolves_legacy_string_waiting(proj):
    st = state.load(proj)
    st["waiting"] = "точка 1"
    state.save(proj, st)
    assert state.main(["-p", proj, "resolve", "точка 1", "--summary", "ок", "--minutes", "2"]) == 0
    assert state.load(proj)["waiting"] is None


def test_cli_no_project_code_3(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "empty"))
    assert state.main(["-p", "nope", "show"]) == 3


def test_cli_help_in_russian():
    import subprocess
    import sys

    from tools.common import ROOT
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "state.py"), "--help"], capture_output=True, timeout=60)
    assert r.returncode == 0 and re.search("[а-яё]", r.stdout.decode("utf-8", "replace").lower())
