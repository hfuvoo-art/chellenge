# Тесты analyze.py cell: ячейка таблицы становится fact без участия LLM; без этого табличные факты придётся доверять модели.
import openpyxl
import pytest

from tools import analyze, claims, ingest, tables
from tools.common import project_path


def _xlsx(tmp_path, header2="2024", name="v.xlsx"):
    tmp_path.mkdir(exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Vyezd"
    ws.append(["Страна", header2])
    ws.append(["Турция", 1302417])
    path = tmp_path / name
    wb.save(path)
    return path


def test_analyze_cell_adds_deterministic_fact(tmp_project, tmp_path):
    sid = ingest.ingest(tmp_project, str(_xlsx(tmp_path)), found_by="user")
    assert analyze.main(["-p", tmp_project, "cell", sid, "Vyezd!B2", "--question", "Q1"]) == 0
    (c,) = claims.load(tmp_project)
    cell = tables.get_cell(project_path(tmp_project) / "materials" / f"{sid}.xlsx", "Vyezd!B2")
    assert claims.load(tmp_project)[0]["source"] == sid
    assert c["type"] == "fact" and c["extracted_by"] == "analyze.py"
    assert c["source"] == sid and c["locator"] == "Vyezd!B2" and c["question"] == ["Q1"]
    assert c["quote"] == tables.render(cell) == ingest.section(tmp_project, sid, "Vyezd!B2")
    assert c["value"] == 1302417 and c["dims"] == {"Страна": "Турция", "Год": "2024"}
    assert analyze.main(["-p", tmp_project, "cell", sid, "Vyezd!B2"]) == 0  # повтор не плодит дубликаты
    assert len(claims.load(tmp_project)) == 1
    with pytest.raises(SystemExit):  # не ячейка данных
        analyze.main(["-p", tmp_project, "cell", sid, "Vyezd!A2"])
    # нераспознанная шапка: не fact, а estimate
    bad = _xlsx(tmp_path / "bad", header2=None)
    s2 = ingest.ingest(tmp_project, str(bad), found_by="user")
    assert analyze.main(["-p", tmp_project, "cell", s2, "Vyezd!B2"]) == 0
    assert claims.load(tmp_project)[-1]["type"] == "estimate"


def test_analyze_cell_xlsm(tmp_project, tmp_path):
    sid = ingest.ingest(tmp_project, str(_xlsx(tmp_path / "m", name="m.xlsm")), found_by="user")
    assert analyze.main(["-p", tmp_project, "cell", sid, "Vyezd!B2"]) == 0
    assert claims.load(tmp_project)[0]["value"] == 1302417
