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


# ---------- профиль данных и расчёты (задача 18) ----------

def _quarterly_xlsx(tmp_path, skip=None, name="q.xlsx"):
    tmp_path.mkdir(exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Vyezd"
    cols = [(y, q) for y in (2023, 2024) for q in (1, 2, 3, 4) if (y, q) != skip]
    ws.append([None] + [str(y) for y, _ in cols])  # год в каждой ячейке шапки, без объединений
    ws.append([None] + [f"{'I' * q if q < 4 else 'IV'} квартал" for _, q in cols])
    ws.append(["Турция"] + [100 + 10 * i for i in range(len(cols))])
    path = tmp_path / name
    wb.save(path)
    return path


def test_profile_basic_sections(tmp_project, tmp_path):
    sid = ingest.ingest(tmp_project, str(_quarterly_xlsx(tmp_path)), found_by="user")
    out = analyze.profile(tmp_project, sid)
    assert out == project_path(tmp_project) / "calc" / f"profile-{sid}.md"
    txt = out.read_text(encoding="utf-8")
    for h in ("## Размер (N)", "## Единицы", "## Периоды и пропуски", "## Дубликаты", "## Выбросы"):
        assert h in txt
    assert "пропусков кварталов нет" in txt and "ПРОПУЩЕННЫЙ" not in txt


def test_period_gap_flagged(tmp_project, tmp_path):
    sid = ingest.ingest(tmp_project, str(_quarterly_xlsx(tmp_path, skip=(2023, 3))), found_by="user")
    txt = analyze.profile(tmp_project, sid).read_text(encoding="utf-8")
    assert "ПРОПУЩЕННЫЙ КВАРТАЛ" in txt and "2023-Q3" in txt
    assert analyze.main(["-p", tmp_project, "profile", sid]) == 0


def test_profile_rejects_non_table(tmp_project):
    with pytest.raises(ValueError, match="нет в проекте"):
        analyze.profile(tmp_project, "S-099")


def _calc(tmp_project, cid, body):
    d = project_path(tmp_project) / "calc"
    d.mkdir(exist_ok=True)
    (d / f"{cid}.py").write_text(body, encoding="utf-8")


def test_calc_reproduces_estimate(tmp_project, capsys):
    _calc(tmp_project, "C-021", "print('промежуточно 1')\nprint('RESULT=32,6 млн ₽ в год')\n")
    assert analyze.run_calc(tmp_project, "C-021") == pytest.approx(32.6)
    assert analyze.main(["-p", tmp_project, "calc", "C-021"]) == 0
    assert "RESULT=32.6" in capsys.readouterr().out
    _calc(tmp_project, "C-022", "print('нет результата')\n")
    with pytest.raises(ValueError, match="RESULT"):
        analyze.run_calc(tmp_project, "C-022")
    _calc(tmp_project, "C-023", "raise SystemExit(3)\n")
    with pytest.raises(ValueError, match="ошибкой"):
        analyze.run_calc(tmp_project, "C-023")
    _calc(tmp_project, "C-024", "import time; time.sleep(5)\n")
    with pytest.raises(ValueError, match="не уложился"):
        analyze.run_calc_ex(tmp_project, "C-024", timeout=0.5)
    with pytest.raises(ValueError, match="нет"):
        analyze.run_calc(tmp_project, "C-099")


def test_check3_runs_calc_for_estimate(tmp_project):
    from tools import check
    cid = claims.add(tmp_project, {"type": "estimate", "text": "рынок около 32,6 млн ₽ в год", "source": "S-001",
                                   "locator": "calc/C-001.py", "quote": "выезды × доли", "extracted_by": "analyze.py"})
    _calc(tmp_project, cid, "print('RESULT=32.6 млн ₽ в год')\n")
    assert [x.level for x in check.run(tmp_project, {3})] == ["OK"]
    _calc(tmp_project, cid, "print('RESULT=40.1 млн ₽ в год')\n")  # расхождение с записью
    f = check.run(tmp_project, {3})
    assert [x.level for x in f] == ["FAIL"] and "40.1" in f[0].msg
    _calc(tmp_project, cid, "print('RESULT=32.6 %')\n")  # то же число, другая единица
    assert [x.level for x in check.run(tmp_project, {3})] == ["FAIL"]
    _calc(tmp_project, cid, "raise RuntimeError('boom')\n")
    f = check.run(tmp_project, {3})
    assert [x.level for x in f] == ["FAIL"] and "ошибкой" in f[0].msg
