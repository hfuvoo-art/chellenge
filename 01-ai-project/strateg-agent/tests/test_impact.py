# Тесты impact.py: охват пересмотра по слоям и идемпотентная запись блока; без них новый источник пройдёт мимо вариантов, решений и обещаний.
from datetime import date

from tests._graph_fixture import build
from tools import impact
from tools.common import project_path


def test_impact_by_source_lists_all_layers(tmp_project):
    build(tmp_project)
    r = impact.impact(tmp_project, source="S-002")
    assert r.claims == ["C-001", "C-002", "C-003"]      # свои и прошлой версии источника (S-002 заменяет S-001)
    assert r.options == ["O1"]
    assert "Альтернативы" in r.sections
    assert r.decisions == ["D-1", "D-2"]                  # D-2 через depends_on F-1
    assert r.promises == ["F-1"]
    g = impact.graph(tmp_project)
    assert g["source_supersedes"] == {"S-002": "S-001"} and g["claim_source"]["C-001"] == "S-001"


def test_impact_follows_supersedes(tmp_project):
    build(tmp_project)
    r = impact.impact(tmp_project, claim="C-005")
    assert r.claims == ["C-004", "C-005"]
    assert r.options == ["O2"]
    r2 = impact.impact(tmp_project, claim="C-004")
    assert r2.claims == ["C-004", "C-005"]


def test_impact_write_idempotent_per_date(tmp_project):
    root = build(tmp_project)
    r = impact.impact(tmp_project, source="S-002")
    assert impact.write_block(tmp_project, r, today=date(2026, 11, 13), reason="источник S-002") is True
    once = (root / "strategy.md").read_text(encoding="utf-8")
    assert once.count("## Пересмотр от 2026-11-13") == 1 and "O1" in once and "D-1" in once
    assert impact.write_block(tmp_project, r, today=date(2026, 11, 13), reason="источник S-002") is False
    assert (root / "strategy.md").read_text(encoding="utf-8") == once
    assert impact.write_block(tmp_project, r, today=date(2026, 11, 14), reason="источник S-002") is True
    assert (root / "strategy.md").read_text(encoding="utf-8").count("## Пересмотр от") == 2
    # блок не создаёт ссылок на заменённые утверждения (check.py проверка 4)
    r2 = impact.impact(tmp_project, claim="C-005")
    impact.write_block(tmp_project, r2, today=date(2026, 12, 1), reason="C-005")
    tail = (project_path(tmp_project) / "strategy.md").read_text(encoding="utf-8").split("## Пересмотр от 2026-12-01")[1]
    assert "C-004" not in tail


def test_impact_rewrite_after_supersede_keeps_agent_text(tmp_project):
    from tools import check, claims
    root = build(tmp_project)
    d = date(2026, 11, 13)
    r = impact.impact(tmp_project, source="S-002")
    impact.write_block(tmp_project, r, today=d, reason="источник S-002")
    p = root / "strategy.md"
    p.write_text(p.read_text(encoding="utf-8") + "\nТекст агента: цена выросла, решение D-1 затронуто.\n", encoding="utf-8")
    claims.set_status(tmp_project, "C-002", "superseded", by="C-003", reason="новая версия")
    p.write_text(p.read_text(encoding="utf-8").replace("Цена [C-002].", "Цена [C-003]."), encoding="utf-8")  # агент заменил ссылку в теле
    before = [f for f in check.check_refs(tmp_project) if f.level == "FAIL" and f.msg.startswith("strategy.md")]
    assert before, "в блоке остался [C-002] после supersede: именно это чинится повторным --write"
    assert impact.write_block(tmp_project, impact.impact(tmp_project, source="S-002"), today=d, reason="источник S-002") is True
    text = p.read_text(encoding="utf-8")
    assert text.count("## Пересмотр от 2026-11-13") == 1 and "Текст агента: цена выросла" in text
    assert "№002 (superseded)" in text
    assert not [f for f in check.check_refs(tmp_project) if f.level == "FAIL" and f.msg.startswith("strategy.md")]


def test_impact_unknown_source_or_claim_rc3(tmp_project, capsys):
    build(tmp_project)
    assert impact.main(["S-999", "-p", tmp_project]) == 3
    assert "S-999" in capsys.readouterr().out
    assert impact.main(["--claim", "C-999", "-p", tmp_project]) == 3
