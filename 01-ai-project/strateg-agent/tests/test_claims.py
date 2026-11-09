# Тесты реестра утверждений: защищают правило «fact только с источником, цитатой и не от агента» и целостность claims.jsonl.
import pytest

from tools import claims
from tools.common import read_jsonl, project_path


def _fact(**kw):
    c = {"text": "Выезды в Турцию выросли", "type": "fact", "source": "S-001", "locator": "p.3",
         "quote": "выезды в Турцию выросли на 12 %", "question": ["Q1"], "extracted_by": "extract.py"}
    c.update(kw)
    return c


def _concl(text="Вывод", **kw):
    c = {"text": text, "type": "conclusion", "extracted_by": "agent:main"}
    c.update(kw)
    return c


def _events(slug):
    return [e for e in read_jsonl(project_path(slug) / "log.jsonl")]


def test_fact_requires_source_locator_quote(tmp_project):
    for missing in ("source", "locator", "quote"):
        c = _fact()
        del c[missing]
        assert any(missing in e for e in claims.validate(c))
        with pytest.raises(ValueError):
            claims.add(tmp_project, c)
    assert claims.load(tmp_project) == []
    assert claims.validate(_fact()) == []


def test_dims_value_only_for_cell_locator(tmp_project):
    cell = _fact(locator="Лист!C14", dims={"Страна": "Турция"}, value=1302417, extracted_by="analyze.py")
    assert claims.validate(cell) == []
    page = _fact(locator="p.12", dims={"Страна": "Турция"}, value=1302417)
    assert claims.validate(page)
    assert claims.validate(_fact(locator="¶37", value=5))
    assert claims.validate(_fact(locator="Лист!C14", value="много", extracted_by="analyze.py"))


def test_agent_written_claim_cannot_be_fact(tmp_project):
    assert claims.validate(_fact(extracted_by="agent:main"))
    assert claims.validate(_fact(extracted_by="agent"))
    assert claims.validate({k: v for k, v in _fact().items() if k != "extracted_by"})
    for who in ("extract.py", "extract.py:spike", "analyze.py", "user"):
        assert claims.validate(_fact(extracted_by=who)) == []
    assert claims.validate(_concl(type="synthetic", extracted_by="agent:main"))
    for t in ("conclusion", "hypothesis", "forecast"):
        assert claims.validate(_concl(type=t)) == []


def test_add_sequential_ids(tmp_project):
    ids = [claims.add(tmp_project, _concl(f"вывод {i}")) for i in range(3)]
    assert ids == ["C-001", "C-002", "C-003"]
    c = claims.get(tmp_project, "C-002")
    assert c["status"] == "active" and c["supersedes"] is None and c["id"] == "C-002"
    assert [x["id"] for x in claims.load(tmp_project)] == ids
    # повторная запись той же формулировки не плодит дубликат
    assert claims.add(tmp_project, _concl("вывод 1")) == "C-002"
    assert len(claims.load(tmp_project)) == 3


def test_supersede_links_and_hides_old(tmp_project):
    old = claims.add(tmp_project, _fact())
    new = claims.add(tmp_project, _fact(text="Выезды в Турцию выросли на 15 %", quote="рост выездов составил 15 %"))
    claims.set_status(tmp_project, old, "superseded", by=new, reason="новые данные")
    assert claims.get(tmp_project, old)["status"] == "superseded"
    assert claims.get(tmp_project, new)["supersedes"] == old
    assert [c["id"] for c in claims.active(tmp_project)] == [new]
    claims.set_status(tmp_project, new, "disputed", reason="расходится с S-002")
    assert [c["id"] for c in claims.active(tmp_project)] == [new]  # disputed остаётся в active()
    with pytest.raises(ValueError):
        claims.set_status(tmp_project, new, "superseded", reason="нет ссылки")


def test_retract_requires_reason_and_logs(tmp_project):
    cid = claims.add(tmp_project, _fact())
    with pytest.raises(ValueError):
        claims.set_status(tmp_project, cid, "retracted", reason="")
    assert claims.get(tmp_project, cid)["status"] == "active"
    claims.set_status(tmp_project, cid, "retracted", by="user", reason="цитата из другого года")
    assert claims.get(tmp_project, cid)["status"] == "retracted"
    assert claims.active(tmp_project) == []
    ev = [e for e in _events(tmp_project) if e["kind"] == "claim_status"]
    assert ev and ev[-1]["id"] == cid and ev[-1]["status"] == "retracted" and "другого года" in ev[-1]["reason"]
    with pytest.raises(KeyError):
        claims.get(tmp_project, "C-099")


def test_search_by_wording(tmp_project):
    claims.add(tmp_project, _fact())
    claims.add(tmp_project, _fact(text="Тариф без абонентской платы подорожал", quote="плата за тариф выросла", locator="p.4"))
    claims.add(tmp_project, _concl("Отток растёт в сегменте молодёжи"))
    res = claims.search(tmp_project, "Турция выезд")
    assert res and res[0]["text"] == "Выезды в Турцию выросли"
    assert claims.search(tmp_project, "Турция выезд", types=["conclusion"]) == []
    assert claims.search(tmp_project, "квантовая гравитация") == []
    assert len(claims.search(tmp_project, "выросли", limit=1)) <= 1


def test_list_filters(tmp_project, capsys):
    a = claims.add(tmp_project, _fact(question=["Q1"]))
    b = claims.add(tmp_project, _concl("гипотеза про отток", type="hypothesis", question=["Q2"]))
    claims.set_status(tmp_project, a, "disputed", reason="спорно")
    assert claims.main(["-p", tmp_project, "list", "--type", "hypothesis"]) == 0
    out = capsys.readouterr().out
    assert b in out and a not in out
    claims.main(["-p", tmp_project, "list", "--question", "Q1"])
    out = capsys.readouterr().out
    assert a in out and b not in out
    claims.main(["-p", tmp_project, "list", "--status", "active"])
    out = capsys.readouterr().out
    assert b in out and a not in out
