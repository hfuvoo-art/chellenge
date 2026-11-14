# Тесты review.py и блока «Пересмотр» статуса: без них просроченные решения и решения на отозванных основаниях не видны на старте сессии.
import json
from datetime import date

from tests._graph_fixture import build
from tools import review, status
from tools.common import project_path


def _dec(i, **kw):
    d = {"id": i, "decision": "x", "owner": "o", "metric": "m", "basis": ["C-006"], "target": "t",
         "deadline": "2027-03-01", "depends_on": [], "revisit_if": [], "status": "active"}
    d.update(kw)
    return d


def _kinds(items):
    return sorted((i.kind, i.decision_id) for i in items)


def test_review_overdue_and_stale_basis(tmp_project):
    build(tmp_project, [
        _dec("D-1", deadline="2026-01-01"),                                   # просрочено
        _dec("D-2", basis=["C-004"]),                                         # C-004 заменено
        _dec("D-3", basis=["C-002"], deadline="2026-01-01", status="done"),   # закрытое не считаем
        _dec("D-4"),                                                          # всё в порядке
    ])
    items = review.review(tmp_project, date(2026, 11, 13))
    assert _kinds(items) == [("overdue", "D-1"), ("stale_basis", "D-2")]
    assert all(i.msg for i in items)
    p = project_path(tmp_project) / "claims.jsonl"
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
    for r in rows:
        if r["id"] == "C-006":
            r["status"] = "retracted"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    assert ("stale_basis", "D-4") in _kinds(review.review(tmp_project, date(2026, 11, 13)))


def test_review_revisit_if_triggered(tmp_project):
    build(tmp_project, [
        _dec("D-1", revisit_if=["источник S-001 заменён новой версией"]),   # S-001 заменён S-002
        _dec("D-2", revisit_if=["цена в C-004 изменилась"]),                # C-004 уже заменено
        _dec("D-3", revisit_if=["доля eSIM < 5 % два квартала подряд"]),    # автоматически не проверяется
        _dec("D-4", status="revisit"),
    ])
    got = _kinds(review.review(tmp_project, date(2026, 11, 13)))
    assert ("revisit", "D-1") in got and ("revisit", "D-2") in got and ("revisit", "D-4") in got
    assert not [k for k in got if k[1] == "D-3"]


def test_review_empty_decisions(tmp_project):
    build(tmp_project)
    (project_path(tmp_project) / "decisions.yaml").write_text("decisions: []\n", encoding="utf-8")
    assert review.review(tmp_project, date(2026, 11, 13)) == []


def test_status_shows_review_items(tmp_project, monkeypatch, tmp_path):
    build(tmp_project, [_dec("D-1", deadline="2020-01-01"), _dec("D-2", basis=["C-004"])])
    monkeypatch.setattr(status.lock, "verify", lambda root: [])
    monkeypatch.setattr(status, "PRICES_PATH", tmp_path / "nope.yaml")
    out = status.render(tmp_project)
    block = out.split("Пересмотр:")[1]
    assert "overdue" in block and "D-1" in block and "stale_basis" in block and "D-2" in block
    assert "нет" not in block.splitlines()[1]
