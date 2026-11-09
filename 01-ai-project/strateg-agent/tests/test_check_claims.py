# Тесты check.py проверки 1–4 и 11 (цитаты, числа, ячейки, ссылки, ключи): без них поддельная цитата или «не та» строка таблицы пройдёт в стратегию.
import sys
from pathlib import Path

import pytest

from tools import claims, ingest, tables
from tools.check import check_numbers, check_quote, check_refs, check_secrets, check_table_fact, run
from tools.common import project_path


def _src(slug, name: str, text: str) -> str:
    p = project_path(slug).parent / name
    p.write_text(text, encoding="utf-8")
    return ingest.ingest(slug, p, found_by="user")


def _fact(sid, loc, text, quote, **kw):
    return {"type": "fact", "text": text, "source": sid, "locator": loc, "quote": quote,
            "extracted_by": "extract.py", **kw}


def _lv(findings):
    return {f.level for f in findings}


def _levels(slug, check):
    return [f.level for f in run(slug) if f.check == check]


# ---- проверка 1: цитата ----

def test_quote_exact_ok():
    f = check_quote({"quote": "рынок вырос на 12%"}, "В 2024 году рынок вырос на 12% к прошлому году.")
    assert f.level == "OK"


def test_quote_fuzzy_warn():
    f = check_quote({"quote": "Рынок eSIM вырос на 12 процентов"}, "Рынок eSIM вырос на 12 процента")
    assert f.level == "WARN" and f.check == 1


def test_negation_mismatch_fail():
    f = check_quote({"quote": "выручка не выросла на 12%"}, "Выручка выросла на 12%.")
    assert f.level == "FAIL" and "отрицан" in f.msg


def test_quote_absent_fail():
    f = check_quote({"quote": "тарифы подешевели вдвое"}, "Абоненты выбирают безлимитные тарифы.")
    assert f.level == "FAIL"


def test_normalization():
    assert check_quote({"quote": "Ёлка «Мир»"}, 'елка "мир" рядом').level == "OK"
    assert check_quote({"quote": "мар-\nкетинг растёт"}, "маркетинг растет быстро").level == "OK"
    assert check_quote({"quote": "а  б в"}, "а б в").level == "OK"


# ---- проверка 2: годы ----

def test_year_not_in_quote_checked_against_as_of():
    c = {"text": "в 2026 году выручка 5 млн", "quote": "выручка 5 млн"}
    assert "FAIL" not in _lv(check_numbers(c, c["quote"], "2026-11-09"))
    assert "FAIL" in _lv(check_numbers(c, c["quote"], "2024-01-01"))
    shifted = {"text": "в 2024 году выручка 5 млн", "quote": "В 2023 году выручка 5 млн"}
    fs = check_numbers(shifted, shifted["quote"], "2024-05-01")  # другой год в цитате: as_of не спасает
    assert "FAIL" in _lv(fs) and any("другой год" in f.msg for f in fs)


def test_year_without_as_of_fail():
    c = {"text": "в 2026 году выручка 5 млн", "quote": "выручка 5 млн"}
    assert "FAIL" in _lv(check_numbers(c, c["quote"], None))


# ---- проверка 3: таблицы, расчёт, наблюдения ----

@pytest.fixture
def table(tmp_project):
    sid = _src(tmp_project, "t.csv", "Страна;2023;2024\nТурция;1100000;1302417\nЕгипет;900000;950000\n")
    path = project_path(tmp_project) / "materials" / f"{sid}.csv"
    cell = next(c for c in tables.parse_csv(path) if c.dims.get("Страна") == "Турция" and c.dims.get("Год") == "2024")
    return tmp_project, sid, path, cell


def _tfact(cell, **over):
    c = {"id": "C-001", "type": "fact", "text": "Выезды: Турция, 2024, 1 302 417", "source": "S-001",
         "locator": cell.locator, "quote": "q", "dims": dict(cell.dims), "value": cell.value, "extracted_by": "analyze.py"}
    c.update(over)
    return c


def test_table_ok(table):
    _, _, path, cell = table
    assert check_table_fact(_tfact(cell), path).level == "OK"


def test_table_wrong_row_fail(table):
    _, _, path, cell = table
    egypt = _tfact(cell, text="Выезды: Египет, 2024, 1 302 417", dims={**cell.dims, "Страна": "Египет"})
    assert check_table_fact(egypt, path).level == "FAIL"
    text_only = _tfact(cell, text="Выезды: Египет, 2024, 1 302 417")
    assert check_table_fact(text_only, path).level == "FAIL"


def test_table_value_mismatch_fail(table):
    _, _, path, cell = table
    assert check_table_fact(_tfact(cell, value=1302418, text="Выезды: Турция, 2024, 1 302 418"), path).level == "FAIL"
    assert check_table_fact(_tfact(cell, text="Выезды: Турция, 2024, 1 302 000"), path).level == "FAIL"


def test_estimate_needs_calc_script(tmp_project):
    claims.add(tmp_project, {"type": "estimate", "text": "рынок 5 млн ₽", "source": "S-001",
                             "locator": "calc/C-001.py", "quote": "выезды × доли", "extracted_by": "analyze.py"})
    assert _levels(tmp_project, 3) == ["FAIL"]
    calc = project_path(tmp_project) / "calc"
    calc.mkdir(exist_ok=True)
    (calc / "other.py").write_text("print('RESULT=1 x')\n", encoding="utf-8")
    assert _levels(tmp_project, 3) == ["FAIL"]  # calc/<C-id>.py — именно по id утверждения
    (calc / "C-001.py").write_text("print('RESULT=5000000 ₽')\n", encoding="utf-8")
    assert _levels(tmp_project, 3) == ["OK"]


def test_observation_needs_file_and_zone(tmp_project):
    obs = {"type": "observation", "text": "кнопка внизу экрана", "source": "S-007", "quote": "кнопка «Купить»",
           "locator": "S-007.png#bottom", "extracted_by": "ux-observer"}
    claims.add(tmp_project, obs)
    assert _levels(tmp_project, 3) == ["FAIL"]  # файла нет
    mat = project_path(tmp_project) / "materials"
    mat.mkdir(exist_ok=True)
    (mat / "S-007.png").write_bytes(b"\x89PNG")
    assert _levels(tmp_project, 3) == ["OK"]
    (project_path(tmp_project) / "claims.jsonl").unlink()
    claims.add(tmp_project, {**obs, "locator": "S-007.png"})  # зоны нет
    assert _levels(tmp_project, 3) == ["FAIL"]


# ---- проверка 4: ссылки ----

def test_refs_missing_or_retracted_fail(tmp_project):
    claims.add(tmp_project, {"type": "hypothesis", "text": "h1", "extracted_by": "agent:x"})
    claims.add(tmp_project, {"type": "hypothesis", "text": "h2", "extracted_by": "agent:x"})
    claims.set_status(tmp_project, "C-002", "retracted", reason="неверно")
    proj = project_path(tmp_project)
    (proj / "options.md").write_text("# Варианты\n<!-- шаблон [C-099] -->\n- В1: ок [C-001]\n", encoding="utf-8")
    assert not [f for f in check_refs(tmp_project) if f.level == "FAIL"]
    (proj / "strategy.md").write_text("Опора [C-002] и [C-050].", encoding="utf-8")
    fs = [f for f in check_refs(tmp_project) if f.level == "FAIL"]
    assert {f.target for f in fs} == {"C-002", "C-050"}


# ---- проверка 11: ключи ----

def test_secret_patterns_found(tmp_path):
    keys = {"a.md": "ключ " + "AQV" + "N" + "x" * 30, "b.md": "token = " + "s" + "k-" + "A1" * 12,
            "c.md": "Authorization: " + "Bear" + "er " + "abc123" * 5}
    for n, t in keys.items():
        (tmp_path / n).write_text(t, encoding="utf-8")
    (tmp_path / "ok.md").write_text("шаблоны: AQVN…, sk-…, Bearer <token>", encoding="utf-8")
    fs = check_secrets(tmp_path)
    assert {Path(f.target).name for f in fs if f.level == "FAIL"} == {"a.md", "b.md", "c.md"}
    assert all("x" * 10 not in f.msg and "A1A1A1" not in f.msg for f in fs)  # сам ключ в отчёт не попадает


def test_secrets_skip_env_and_venv(tmp_path):
    (tmp_path / ".env").write_text("K=" + "AQV" + "N" + "y" * 30, encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "x.txt").write_text("s" + "k-" + "Z9" * 12, encoding="utf-8")
    assert not [f for f in check_secrets(tmp_path) if f.level == "FAIL"]


# ---- run: текстовый факт целиком ----

def test_run_text_fact_ok_and_fail(tmp_project):
    sid = _src(tmp_project, "d.txt", "Рынок eSIM в 2024 году вырос на 12% к 2023 году.\n\nДругой абзац.")
    claims.add(tmp_project, _fact(sid, "¶1", "Рынок eSIM вырос на 12%", "Рынок eSIM в 2024 году вырос на 12%"))
    assert all(f.level == "OK" for f in run(tmp_project) if f.check in (1, 2, 3))
    (project_path(tmp_project) / "claims.jsonl").unlink()
    claims.add(tmp_project, _fact(sid, "¶1", "Рынок eSIM вырос на 15%", "Рынок eSIM в 2024 году вырос на 15%"))
    assert any(f.level == "FAIL" for f in run(tmp_project))


# ---- правки по ревью задачи 8 ----

def test_no_tool_module_shadows_stdlib():
    root = Path(__file__).resolve().parent.parent
    assert not ({p.stem for p in (root / "tools").glob("*.py")} & sys.stdlib_module_names)


def test_run_rejects_invalid_fact(tmp_project):
    import json
    rows = [{"id": "C-001", "type": "fact", "text": "доля 5%", "status": "active", "extracted_by": "extract.py"},
            {"id": "C-002", "type": "fact", "text": "x", "source": "S-001", "locator": "¶1", "quote": "x",
             "status": "active", "extracted_by": "agent:main"}]
    (project_path(tmp_project) / "claims.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    fs = [f for f in run(tmp_project, {1}) if f.level == "FAIL"]
    assert {f.target for f in fs} == {"C-001", "C-002"}


def test_quote_truncated_after_negation_fail():
    f = check_quote({"quote": "выросла на 12% за год"}, "Выручка не выросла на 12% за год.")
    assert f.level == "FAIL" and "отрицан" in f.msg


def test_short_ref_ids_checked(tmp_project):
    (project_path(tmp_project) / "strategy.md").write_text("Опора [C-14].", encoding="utf-8")
    assert {f.target for f in check_refs(tmp_project) if f.level == "FAIL"} == {"C-14"}


def test_secret_target_is_relative(tmp_path):
    (tmp_path / "a.md").write_text("k " + "AQV" + "N" + "x" * 30, encoding="utf-8")
    assert [f.target for f in check_secrets(tmp_path) if f.level == "FAIL"] == ["a.md"]


def test_usage_error_exit_code_3(capsys):
    from tools.check import main
    with pytest.raises(SystemExit) as e:
        main(["--only", "99"])
    assert e.value.code == 3
    with pytest.raises(SystemExit) as e:
        main(["--bogus"])
    assert e.value.code == 3


def test_secret_in_big_file_found(tmp_path):
    key = "AQV" + "N" + "x" * 30
    (tmp_path / "big.md").write_text("a\n" * 1_100_000 + "k " + key + "\n", encoding="utf-8")
    assert [f.level for f in check_secrets(tmp_path)] == ["FAIL"]
