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
