# Тесты check.py проверки 5–10 (варианты, разделы стратегии, обещания, план проверки, основания, пробелы), подтверждение WARN, лимит итераций и отчёт: без них пустая или «для галочки» стратегия уйдёт к руководителю.
import json
import shutil
from pathlib import Path

import pytest

from tools import check, state
from tools.check import (check_basis, check_options, check_promises_static, check_strategy_sections, check_test_plan,
                         check_unknowns, run)
from tools.common import project_path

FIX = Path(__file__).parent / "fixtures" / "proj-ok"
ALL_BUT_LOCK = "1,2,3,4,5,6,7,8,9,10"


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    shutil.copytree(FIX, tmp_path / "projects" / "ok")
    return "ok"


def edit(slug, name, old, new, count=1):
    p = project_path(slug) / name
    text = p.read_text(encoding="utf-8")
    assert old in text, f"в {name} нет фрагмента {old!r}"
    p.write_text(text.replace(old, new, count), encoding="utf-8")


def levels(findings):
    return {f.level for f in findings}


def fails(findings):
    return [f for f in findings if f.level == "FAIL"]


def set_claims(slug, mutate):
    p = project_path(slug) / "claims.jsonl"
    items = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    mutate(items)
    p.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in items), encoding="utf-8")


def set_thesis(slug, thesis_lines: str):
    p = project_path(slug) / "strategy.md"
    t = p.read_text(encoding="utf-8")
    a, b = t.index("## Рекомендация\n") + len("## Рекомендация\n"), t.index("## Продуктовая стратегия")
    p.write_text(t[:a] + "\nРешение: упростить активацию.\n\n" + thesis_lines.rstrip() + "\n\n" + t[b:], encoding="utf-8")


def rc(argv):
    """Код выхода CLI: die() завершает процесс исключением SystemExit."""
    try:
        return check.main(argv)
    except SystemExit as e:
        return e.code


def report(slug):
    return (project_path(slug) / "check-report.md").read_text(encoding="utf-8")


def test_fixture_project_passes_checks_5_to_10(proj):
    res = run(proj, {5, 6, 7, 8, 9, 10})
    assert not fails(res) and "WARN" not in levels(res), [(f.check, f.target, f.msg) for f in res if f.level != "OK"]


# ---- проверка 5 ----

def test_options_min3_with_status_quo_and_close(proj):
    assert levels(check_options(proj)) == {"OK"}
    p = project_path(proj) / "options.md"
    text = p.read_text(encoding="utf-8")
    p.write_text(text[:text.index("## O3")], encoding="utf-8")
    assert any("меньше 3" in f.msg for f in fails(check_options(proj)))
    p.write_text(text.replace("· close ·", "· other ·"), encoding="utf-8")
    assert any("close" in f.msg for f in fails(check_options(proj)))
    p.write_text(text.replace("· status_quo ·", "· other ·"), encoding="utf-8")
    assert any("status_quo" in f.msg for f in fails(check_options(proj)))


def test_options_template_and_missing_file_fail(proj):
    p = project_path(proj) / "options.md"
    p.write_text("# Варианты\n\n<!-- ## O1 · status_quo · Пример\nВозражения:\n- В1: x [C-001]\n-->\n", encoding="utf-8")
    assert fails(check_options(proj))  # пример в комментарии не считается вариантом
    p.unlink()
    assert any("options.md" in f.msg for f in fails(check_options(proj)))


def test_objections_two_and_one_with_ref(proj):
    edit(proj, "options.md", "- В2: Конкуренты упрощают активацию, мы отстанем (гипотеза).\n", "")
    f = fails(check_options(proj))
    assert f and f[0].target == "O1" and "возраж" in f[0].msg
    edit(proj, "options.md", "- В1: Без действий барьер активации остаётся, 18 из 40 опрошенных называют его главным [C-002].\n",
         "- В1: Без действий барьер активации остаётся.\n- В2: Конкуренты упрощают активацию (гипотеза).\n")
    f = fails(check_options(proj))
    assert f and f[0].target == "O1" and "ссылк" in f[0].msg


def test_objection_ref_must_point_to_live_claim(proj):
    edit(proj, "options.md", "[C-002].\n- В2: Конкуренты", "[C-099].\n- В2: Конкуренты")
    assert any(f.target == "O1" and "ссылк" in f.msg for f in fails(check_options(proj)))
    edit(proj, "options.md", "[C-099]", "[C-002]")
    set_claims(proj, lambda cs: [c.update(status="retracted") for c in cs if c["id"] == "C-002"])
    assert any(f.target == "O1" for f in fails(check_options(proj)))


# ---- проверка 6 ----

def test_strategy_required_headings(proj):
    assert levels(check_strategy_sections(proj)) == {"OK"}
    edit(proj, "strategy.md", "### Осознанные отказы\n", "")
    f = fails(check_strategy_sections(proj))
    assert f and "Осознанные отказы" in f[0].msg


def test_strategy_wrong_level_or_empty_section_fails(proj):
    edit(proj, "strategy.md", "## Чего мы не знаем", "### Чего мы не знаем")
    assert any("Чего мы не знаем" in f.msg for f in fails(check_strategy_sections(proj)))
    edit(proj, "strategy.md", "### Чего мы не знаем", "## Чего мы не знаем")
    edit(proj, "strategy.md", "Абонент перед сменой телефона.\n", "")
    assert any("Аудитория и ситуация" in f.msg and "пуст" in f.msg for f in fails(check_strategy_sections(proj)))


def test_strategy_template_untouched_fails(proj):
    tpl = Path(__file__).resolve().parent.parent / "projects" / "_template" / "strategy.md"
    (project_path(proj) / "strategy.md").write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")
    assert fails(check_strategy_sections(proj))


# ---- проверка 7 ----

def test_promise_needs_existing_feature_and_date_if_planned(proj):
    assert levels(check_promises_static(proj)) == {"OK"}
    edit(proj, "strategy.md", "→ F-2", "→ F-9")
    assert any("F-9" in f.msg for f in fails(check_promises_static(proj)))
    edit(proj, "strategy.md", "→ F-9", "→ F-2")
    edit(proj, "product.yaml", "available_from: 2027-Q1", "available_from: null")
    assert any("F-2" in f.msg and "срок" in f.msg for f in fails(check_promises_static(proj)))
    edit(proj, "product.yaml", "available_from: null", "available_from: 2027-Q1")
    edit(proj, "strategy.md", "- «Перенос номера в один шаг» → F-2", "- «Перенос номера в один шаг»")
    assert any("F-n" in f.msg for f in fails(check_promises_static(proj)))


def test_promise_bad_feature_status_fails(proj):
    edit(proj, "product.yaml", "status: exists", "status: maybe")
    assert any("F-1" in f.msg for f in fails(check_promises_static(proj)))


# ---- проверка 8 ----

def test_test_plan_four_parts(proj):
    assert levels(check_test_plan(proj)) == {"OK"}
    edit(proj, "strategy.md", "### База сравнения\nОпрос до запуска: 18 из 40 (45%) [C-002].\n", "")
    assert any("База сравнения" in f.msg for f in fails(check_test_plan(proj)))
    edit(proj, "strategy.md", "3 месяца после запуска.", "")
    assert any("Срок наблюдения" in f.msg for f in fails(check_test_plan(proj)))
    edit(proj, "strategy.md", "Рост обращений в поддержку по переносу номера: не больше +10% к текущему уровню.", "...")
    assert any("Нежелательные последствия" in f.msg for f in fails(check_test_plan(proj)))


def test_test_plan_expected_change_needs_number(proj):
    edit(proj, "strategy.md", "снижается с 45% до 20%", "снижается заметно")
    assert any("Ожидаемое изменение" in f.msg for f in fails(check_test_plan(proj)))


# ---- проверка 9 ----

def test_basis_not_only_synthetic_n1_or_suspicious(proj):
    assert levels(check_basis(proj)) == {"OK"}
    set_thesis(proj, "- Т1: Абоненты не понимают перенос номера [C-003].")
    f = fails(check_basis(proj))
    assert f and "synthetic" in f[0].msg
    set_thesis(proj, "- Т1: Рост сегмента [C-001].")  # источник помечен suspicious
    edit(proj, "sources.yaml", "suspicious: []", "suspicious: ['¶1']")
    f = fails(check_basis(proj))
    assert f and "suspicious" in f[0].msg


def test_basis_interview_n1_fails_n2_ok(proj):
    def to_interview(cs):
        for c in cs:
            if c["id"] == "C-003":
                c["type"] = "interview"
                c["extracted_by"] = "extract.py"
        cs.append({"id": "C-005", "type": "interview", "text": "Респондент R-1 боится потерять номер", "source": "S-002",
                   "locator": "¶1", "quote": "[SYNTHETIC] Мне непонятно, как перенести номер на eSIM.",
                   "extracted_by": "extract.py", "respondent": "R-1", "status": "active", "question": ["Q1"], "supersedes": None})
    set_claims(proj, to_interview)
    set_thesis(proj, "- Т1: Перенос номера пугает [C-003], [C-005].")
    f = fails(check_basis(proj))
    assert f and "interview" in f[0].msg
    set_claims(proj, lambda cs: [c.update(respondent="R-2") for c in cs if c["id"] == "C-005"])
    assert not fails(check_basis(proj))


def test_basis_thesis_needs_valid_refs_and_theses(proj):
    set_thesis(proj, "- Т1: Утверждение без ссылки.")
    assert any("ссыл" in f.msg for f in fails(check_basis(proj)))
    set_thesis(proj, "Просто текст без тезисов.")
    assert any("тезис" in f.msg for f in fails(check_basis(proj)))
    set_thesis(proj, "- Т1: Ссылка в никуда [C-077].")
    assert fails(check_basis(proj))


def test_basis_mixed_synthetic_and_fact_ok(proj):
    set_thesis(proj, "- Т1: Сегмент растёт [C-001], перенос номера непонятен [C-003].")
    assert not fails(check_basis(proj))


# ---- проверка 10 ----

def test_unknowns_nonempty_and_format(proj):
    assert levels(check_unknowns(proj)) == {"OK"}
    good = "- Не знаем, как доля eSIM растёт по регионам, потому что отчёт даёт только среднее. Узнать так: запросить региональные данные у автора отчёта.\n"
    edit(proj, "strategy.md", good, "")
    assert fails(check_unknowns(proj))
    edit(proj, "strategy.md", "## Чего мы не знаем\n", "## Чего мы не знаем\n- Всё и так понятно.\n")
    f = fails(check_unknowns(proj))
    assert f and "формат" in f[0].msg
    edit(proj, "strategy.md", "- Всё и так понятно.\n", "- Не знаем X, потому что Y. Узнать так: Z.\n")
    assert not fails(check_unknowns(proj))


# ---- замечания журнала сборки ----

def _write_s001(proj, p1):
    (project_path(proj) / "materials" / "S-001.md").write_text(
        "<!-- S-001 | report.md | 2026-11-10T12:00:00+03:00 | x | 2026-10-01 -->\n\n<!-- ¶1 -->\n" + p1 + "\n\n<!-- ¶2 -->\n"
        "Из 40 опрошенных 18 человек назвали сложность активации главным барьером.\n", encoding="utf-8")


def test_negation_across_sentence_boundary_not_false_fail(proj):
    _write_s001(proj, "Нет. Доля пользователей eSIM среди абонентов выросла на 12% за 2025 год.")
    res = [f for f in run(proj, {1}) if f.target == "C-001"]
    assert res and levels(res) == {"OK"}, [f.msg for f in res]


def test_negation_cut_off_before_quote_still_fails(proj):
    _write_s001(proj, "Доля пользователей eSIM среди абонентов не выросла на 12% за 2025 год.")
    edit(proj, "claims.jsonl", "Доля пользователей eSIM среди абонентов выросла на 12% за 2025 год.\", \"extracted_by",
         "выросла на 12% за 2025 год.\", \"extracted_by")
    assert "FAIL" in levels([f for f in run(proj, {1}) if f.target == "C-001"])


def test_fact_only_on_suspicious_paragraph_warns(proj):
    edit(proj, "sources.yaml", "suspicious: []", "suspicious: ['¶1']")
    res = [f for f in run(proj, {1}) if f.target == "C-001"]
    assert "WARN" in levels(res) and any("suspicious" in f.msg for f in res)
    assert "FAIL" not in levels(res)


# ---- подтверждение WARN ----

def _fuzzy_quote(proj):
    edit(proj, "claims.jsonl", "среди абонентов выросла на 12% за 2025 год.\", \"extracted_by",
         "среди абонетов выросла на 12% за 2025 год.\", \"extracted_by")


def test_confirm_clears_warn_logs_minutes(proj):
    _fuzzy_quote(proj)
    assert check.main(["-p", proj, "--only", "1"]) == 2
    assert check.main(["-p", proj, "--only", "1", "--confirm", "C-001", "--minutes", "2"]) == 0
    st = state.load(proj)
    assert st["human"][-1]["minutes"] == 2 and "C-001" in st["human"][-1]["summary"]
    log = [json.loads(x) for x in (project_path(proj) / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(e["kind"] == "human" and e.get("minutes") == 2 for e in log)
    assert check.main(["-p", proj, "--only", "1"]) == 0  # подтверждение сохранилось
    n = len(state.load(proj)["human"])
    check.main(["-p", proj, "--only", "1", "--confirm", "C-001", "--minutes", "2"])
    assert len(state.load(proj)["human"]) == n  # повтор не удваивает минуты
    edit(proj, "claims.jsonl", "абонетов", "абонентво")  # цитату поменяли: подтверждение недействительно
    assert check.main(["-p", proj, "--only", "1"]) == 2


def test_confirm_needs_warn_and_minutes(proj, capsys):
    assert rc(["-p", proj, "--only", "1", "--confirm", "C-001", "--minutes", "1"]) == 3
    _fuzzy_quote(proj)
    assert rc(["-p", proj, "--only", "1", "--confirm", "C-001"]) == 3
    assert rc(["-p", proj, "--only", "1", "--confirm", "C-001", "--minutes", "-1"]) == 3


def test_confirm_does_not_clear_fail(proj):
    edit(proj, "claims.jsonl", "выросла на 12% за 2025 год.\", \"extracted_by", "выросла на 99% за 2025 год.\", \"extracted_by")
    assert rc(["-p", proj, "--only", "1", "--confirm", "C-001", "--minutes", "1"]) == 3  # у FAIL нет WARN: подтверждать нечего
    assert check.main(["-p", proj, "--only", "1"]) == 1


# ---- лимит итераций ----

def test_third_fail_waits_for_human(proj):
    edit(proj, "strategy.md", "Абонент перед сменой телефона.\n", "")
    for _ in (1, 2):
        assert check.main(["-p", proj, "--only", "6"]) == 1
        assert state.load(proj)["waiting"] is None
    assert check.main(["-p", proj, "--only", "6"]) == 1
    w = state.load(proj)["waiting"]
    assert w and w["point"] == "check" and w["question"].startswith("Не прошло проверку:")
    assert "Аудитория и ситуация" in w["question"]
    edit(proj, "strategy.md", "### Аудитория и ситуация\n", "### Аудитория и ситуация\nАбонент перед сменой телефона.\n")
    assert check.main(["-p", proj, "--only", "6"]) == 0
    st = state.load(proj)
    assert st["waiting"] is None and not st.get("check_fails")


def test_fail_streak_not_reset_by_unrelated_pass(proj):
    edit(proj, "strategy.md", "Абонент перед сменой телефона.\n", "")
    check.main(["-p", proj, "--only", "6"])
    check.main(["-p", proj, "--only", "5"])  # проверка 5 прошла, но 6 всё ещё красная
    check.main(["-p", proj, "--only", "6"])
    check.main(["-p", proj, "--only", "6"])
    assert state.load(proj)["waiting"]["point"] == "check"


# ---- отчёт и коды выхода ----

def test_report_and_exit_codes(proj):
    assert check.main(["-p", proj, "--only", ALL_BUT_LOCK]) == 0
    rep = report(proj)
    assert "PASS" in rep and "п.5" in rep
    _fuzzy_quote(proj)
    assert check.main(["-p", proj, "--only", ALL_BUT_LOCK]) == 2
    rep = report(proj)
    assert "WARN" in rep and "--confirm C-001" in rep
    edit(proj, "options.md", "## O2 · close ·", "## O2 · other ·")
    assert check.main(["-p", proj, "--only", ALL_BUT_LOCK]) == 1
    rep = report(proj)
    assert "FAIL" in rep and "close" in rep


def test_report_has_no_absolute_paths(proj, tmp_path):
    check.main(["-p", proj, "--only", ALL_BUT_LOCK])
    assert str(tmp_path) not in report(proj)


def test_only_accepts_5_to_10_and_rejects_unknown(proj):
    assert check.main(["-p", proj, "--only", "5,10"]) == 0
    assert rc(["-p", proj, "--only", "12"]) == 3


def test_help_in_russian(capsys):
    with pytest.raises(SystemExit) as e:
        check.main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "--confirm" in out and "--minutes" in out and "итерац" in out
