# Тесты tables.py: разбор шапок, объединённых ячеек, примечаний и формата строки ячейки; без них «неверная строка таблицы» уйдёт в факты незамеченной.
import openpyxl

from tools import ingest, tables
from tools.common import project_path, read_text, read_yaml


def make_wb(path, sheets, merges=None):
    """sheets: {имя: [строки]}; merges: {имя: ['B1:C1', …]}."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
        for m in (merges or {}).get(name, []):
            ws.merge_cells(m)
    wb.save(path)
    return path


def test_header_above_first_numeric_row(tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {"Лист": [
        ["Отчёт по выезду", None],
        ["Страна", "Цена"],
        ["Турция", 100],
        ["Греция", 200.5],
    ]})
    cells = tables.parse_workbook(p)
    assert [c.ref for c in cells] == ["B3", "B4"]
    assert cells[0].dims == {"Страна": "Турция", "Показатель": "Цена"}
    assert cells[0].value == 100 and cells[1].value == 200.5
    assert all(c.header_ok for c in cells)


def test_merged_header_expanded(tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {"Данные": [
        [None, "2023", None, "2024", None],
        [None, "I квартал", "II квартал", "I квартал", "II квартал"],
        ["Турция", 1, 2, 3, 4],
    ]}, merges={"Данные": ["B1:C1", "D1:E1"]})
    cells = tables.parse_workbook(p)
    assert [(c.dims["Год"], c.dims["Квартал"], c.value) for c in cells] == [
        ("2023", "1", 1), ("2023", "2", 2), ("2024", "1", 3), ("2024", "2", 4)]
    assert cells[0].dims["col1"] == "Турция"  # у столбца нет заголовка → col<N>


def test_roman_quarters_normalized(tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {"Д": [
        ["Страна", "2024", None, None, None],
        [None, "I квартал", "II квартал", "III квартал", "IV квартал"],
        ["Турция", 1, 2, 3, 4],
    ]}, merges={"Д": ["B1:E1"]})
    cells = tables.parse_workbook(p)
    assert [c.dims["Квартал"] for c in cells] == ["1", "2", "3", "4"]
    assert all(c.dims["Год"] == "2024" for c in cells)


def test_unknown_header_flagged(tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {"Л": [
        ["Страна", "Цена", None],
        ["Турция", 10, 20],
    ]})
    ok, bad = tables.parse_workbook(p)
    assert ok.header_ok and not bad.header_ok
    assert "[заголовок?]" in tables.render(bad) and "[заголовок?]" not in tables.render(ok)


def test_footnote_rows_not_cells(tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {"Л": [
        ["Страна", "Цена"],
        ["Турция", 10],
        ["Греция", 20],
        [None, None],
        ["Примечание: данные предварительные 2024", None],
        ["* оценка 12", 12],
        ["Источник: Росстат", None],
    ]})
    cells, notes = tables.parse_table(p)
    assert [c.ref for c in cells] == ["B2", "B3"]
    assert [r for r, _ in notes] == ["Л!A5", "Л!A6", "Л!A7"]
    assert "предварительные" in notes[0][1]


def test_multiple_sheets_prefixed(tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {
        "Лист1": [["Страна", "Цена"], ["Турция", 1]],
        "Лист2": [["Страна", "Цена"], ["Греция", 2]],
    })
    cells = tables.parse_workbook(p)
    assert [tables.render(c).split(" ")[0] for c in cells] == ["Лист1!B2", "Лист2!B2"]
    c = tables.get_cell(p, "Лист2!B2")
    assert c.value == 2 and c.dims["Страна"] == "Греция"
    import pytest
    with pytest.raises(ValueError):
        tables.get_cell(p, "Лист3!B2")


def test_render_exact_format():
    c = tables.Cell("Vyezd", "C14", {"Страна": "Турция", "Год": "2024", "Квартал": "3"}, 1302417, True)
    assert tables.render(c) == "Vyezd!C14 [Страна=Турция; Год=2024; Квартал=3] = 1 302 417"
    c2 = tables.Cell("V", "A1", {"Страна": "Греция"}, -1234.5, False)
    assert tables.render(c2) == "V!A1 [Страна=Греция] [заголовок?] = -1 234,5"


def test_ingest_xlsx_writes_cell_lines(tmp_project, tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {"Лист": [
        ["Страна", "Цена"], ["Турция", 1302417], ["Примечание: тест", None]]})
    sid = ingest.ingest(tmp_project, str(p), found_by="user")
    md = read_text(project_path(tmp_project) / "materials" / f"{sid}.md")
    line = "Лист!B2 [Страна=Турция; Показатель=Цена] = 1 302 417"
    assert line in md.splitlines()
    assert ingest.section(tmp_project, sid, "Лист!B2") == line
    assert ingest.section(tmp_project, sid, "Лист!$b$2") == line  # локатор нормализуется как в get_cell
    assert ingest.section(tmp_project, sid, "Лист!A3").startswith("Лист!A3 [примечание]")
    src = read_yaml(project_path(tmp_project) / "sources.yaml")["sources"][0]
    assert src["kind"] == "table" and src["ext"] == "xlsx" and src["warnings"] == []
    assert (project_path(tmp_project) / "materials" / f"{sid}.xlsx").is_file()
    assert ingest.ingest(tmp_project, str(p), found_by="user") == sid  # повтор не плодит источники


def test_csv_like_sheet(tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("Страна;2023;2024\nТурция;1 302 417;12,5\nГреция;−3;н/д\n", encoding="utf-8-sig")
    cells = tables.parse_csv(f)
    assert [(c.ref, c.value) for c in cells] == [("B2", 1302417), ("C2", 12.5), ("B3", -3), ("C3", "н/д")]
    assert cells[0].sheet == "csv" and cells[0].dims == {"Страна": "Турция", "Год": "2023"}
    assert tables.get_cell(f, "csv!C2").value == 12.5


def test_year_like_values_in_body_are_data(tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {"Л": [
        ["Страна", "2023", "2024"],
        ["Турция", 1, 2],
        ["Греция", 1950, 2010],
    ]})
    cells = tables.parse_workbook(p)
    assert [(c.ref, c.value) for c in cells] == [("B2", 1), ("C2", 2), ("B3", 1950), ("C3", 2010)]


def test_two_tables_on_one_sheet(tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {"Л": [
        ["Страна", "2023", "2024"],
        ["Турция", 1, 2],
        [None, None, None],
        ["Страна", 2025, 2026],
        ["Египет", 7, 8],
    ]})
    cells = tables.parse_workbook(p)
    got = {c.ref: (c.dims["Страна"], c.dims["Год"], c.header_ok) for c in cells}
    assert got == {"B2": ("Турция", "2023", True), "C2": ("Турция", "2024", True),
                   "B5": ("Египет", "2025", True), "C5": ("Египет", "2026", True)}


def _dims_below(cells, ref):
    c = next(c for c in cells if c.ref == ref)
    return (c.dims.get("Страна"), c.dims.get("Год"), c.header_ok)


def test_body_rows_do_not_start_new_table(tmp_path):
    """Строка-группа (объединённая), «нет данных», числа текстом и годы без подписи в теле — не шапка новой таблицы."""
    p = make_wb(tmp_path / "t.xlsx", {"Л": [
        ["Страна", "2023", "2024"],
        ["Турция", 1, 2],
        ["Азия", None, None],
        ["Египет", 3, 4],
        ["Греция", "нет данных", "н.д."],
        ["Кипр", 5, 6],
        ["Мальта", "1 302 417", "1 400 000"],
        ["ОАЭ", 7, 8],
        [None, 1999, 2001],
        ["Катар", 9, 10],
    ]}, merges={"Л": ["A3:C3"]})
    cells = tables.parse_workbook(p)
    for ref, country in [("B4", "Египет"), ("B6", "Кипр"), ("B8", "ОАЭ"), ("B10", "Катар")]:
        assert _dims_below(cells, ref) == (country, "2023", True), ref


def test_ingest_as_of_from_passport_note(tmp_project, tmp_path):
    p = make_wb(tmp_path / "t.xlsx", {
        "Данные": [["Страна", "Цена"], ["Турция", 1]],
        "Паспорт": [["Последнее обновление данных: ", "06.11.2026"]],
    })
    sid = ingest.ingest(tmp_project, str(p), found_by="user")
    src = [s for s in read_yaml(project_path(tmp_project) / "sources.yaml")["sources"] if s["id"] == sid][0]
    assert src["as_of"] == "2026-11-06" and src["as_of_source"] == "header"
