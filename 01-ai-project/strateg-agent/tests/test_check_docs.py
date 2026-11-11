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
    assert st["waiting"]["point"] == "check" and not st.get("check_fails")  # PASS сам ожидание не снимает
    assert "лимит итераций был исчерпан" in report(proj).lower()
    state.resolve_human(proj, "check", "разобрали с человеком", 3)
    assert state.load(proj)["waiting"] is None


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


# ---- правки по ревью (круг 1) ----

TEMPLATE = Path(__file__).resolve().parent.parent / "projects" / "_template"
Q_FULL = "Доля пользователей eSIM среди абонентов выросла на 12% за 2025 год.\", \"extracted_by"


@pytest.mark.parametrize("before,quote", [
    ("Это не подтверждается: доля выросла на 12%.", "подтверждается: доля выросла на 12%."),
    ("Доля не... выросла на 12%.", "выросла на 12%."),
    ("Доля не. выросла на 12%.", "выросла на 12%."),
    ("It does not. works well in 12%.", "works well in 12%."),
])
def test_negation_before_quote_still_fails_review1(proj, before, quote):
    _write_s001(proj, before)
    edit(proj, "claims.jsonl", Q_FULL, quote + "\", \"extracted_by")
    edit(proj, "claims.jsonl", "выросла на 12% за 2025 год\", \"type", "выросла на 12%\", \"type")
    assert "FAIL" in levels([f for f in run(proj, {1}) if f.target == "C-001"])


def test_answer_word_boundary_still_ok(proj):
    _write_s001(proj, "Нет! Доля пользователей eSIM среди абонентов выросла на 12% за 2025 год.")
    assert levels([f for f in run(proj, {1}) if f.target == "C-001"]) == {"OK"}


def test_basis_synthetic_plus_agent_conclusion_fails(proj):
    set_thesis(proj, "- Т1: Перенос номера непонятен [C-003], [C-004].")
    f = fails(check_basis(proj))
    assert f and "synthetic" in f[0].msg


def test_basis_only_conclusion_ok(proj):
    set_thesis(proj, "- Т1: Сложность активации мешает сильнее цены [C-004].")
    assert not fails(check_basis(proj))


def test_template_comments_are_not_content(proj):
    text = (TEMPLATE / "strategy.md").read_text(encoding="utf-8")
    assert "<!--" in text and "Т1" in text and "→ F-1" in text and "Узнать так" in text
    (project_path(proj) / "strategy.md").write_text(text, encoding="utf-8")
    assert any("пуст" in f.msg for f in fails(check_strategy_sections(proj)))
    assert fails(check_basis(proj)) and fails(check_promises_static(proj)) and fails(check_unknowns(proj))


@pytest.mark.parametrize("line", [
    "- Подключите eSIM за 3 минуты → F-1",
    "- «Подключите eSIM за 3 минуты» → **F-1**",
    "- «Подключите eSIM за 3 минуты» → F-1 (в приложении)",
    "- «Подключите eSIM за 3 минуты» → F-1, срок не нужен",
    "- «Подключите eSIM за 3 минуты» -> F-1.",
])
def test_promise_format_variants_accepted(proj, line):
    edit(proj, "strategy.md", "- «Подключите eSIM за 3 минуты» → F-1", line)
    res = check_promises_static(proj)
    assert not fails(res), [f.msg for f in res]


def test_promise_intro_prose_ok_but_no_promise_fails(proj):
    edit(proj, "strategy.md", "### Обещания → функции продукта\n", "### Обещания → функции продукта\nОбещания нашей коммуникации:\n")
    assert not fails(check_promises_static(proj))
    p = project_path(proj) / "strategy.md"
    t = p.read_text(encoding="utf-8")
    a, b = t.index("- «Подключите"), t.index("## План проверки")
    p.write_text(t[:a] + "\n" + t[b:], encoding="utf-8")
    assert any("нет ни одного обещания" in f.msg for f in fails(check_promises_static(proj)))


@pytest.mark.parametrize("thesis", [
    "1. Барьер перехода — сложность активации [C-002].",
    "Т1 — Барьер перехода — сложность активации [C-002].",
    "- **Т1:** Барьер перехода — сложность активации [C-002].",
])
def test_thesis_format_variants_accepted(proj, thesis):
    set_thesis(proj, thesis)
    res = check_basis(proj)
    assert not fails(res) and "тезисов 1" in res[0].msg, [f.msg for f in res]


def test_ref_line_outside_thesis_is_checked(proj):
    set_thesis(proj, "- Т1: Барьер — активация [C-002].\n\nПеренос номера непонятен [C-003].")
    f = fails(check_basis(proj))
    assert f and "synthetic" in f[0].msg


def test_yaml_comment_refs_ignored_fresh_template_passes(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    shutil.copytree(TEMPLATE, tmp_path / "projects" / "fresh")
    assert check.main(["-p", "fresh", "--only", "1,2,3,4"]) == 0


def test_yaml_real_ref_still_checked(proj):
    edit(proj, "decisions.yaml", "decisions: []", "decisions: []\nnote: см. C-099")
    assert any(f.check == 4 and f.target == "C-099" for f in fails(run(proj, {4})))


def test_missing_project_exit_3(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    (tmp_path / "projects").mkdir()
    assert rc(["-p", "nope", "--only", "1"]) == 3


def test_full_run_skips_doc_checks_on_early_step(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])  # п.11 проверяется отдельно
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    shutil.copytree(TEMPLATE, tmp_path / "projects" / "fresh")
    (tmp_path / "projects" / "fresh" / "log.jsonl").touch()
    assert check.main(["-p", "fresh", "--only", "1,2,3,4,11"]) == 0
    capsys.readouterr()
    assert check.main(["-p", "fresh"]) == 0
    out = capsys.readouterr().out
    assert "пропущено: проверки 5, 6, 7, 8, 9, 10" in out and "шаг 0" in out
    assert "пропущено" in report("fresh")
    assert check.main(["-p", "fresh", "--only", "5"]) == 1  # явный --only выполняет всегда


def test_full_run_step4_runs_options_only(proj, capsys, monkeypatch):
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])
    st = state.load(proj)
    st["step"] = {"n": 4, "name": "options"}
    state.save(proj, st)
    (project_path(proj) / "strategy.md").write_text((TEMPLATE / "strategy.md").read_text(encoding="utf-8"), encoding="utf-8")  # стратегия не начата
    check.main(["-p", proj, "--only", "1,2,3,4,5"])
    capsys.readouterr()
    rc_ = check.main(["-p", proj])
    out = capsys.readouterr().out
    assert "пропущено: проверки 6, 7, 8, 9, 10" in out and "FAIL" not in out.split("Итого")[0]


# ---- правки по ревью (круг 2) ----

def _break_strategy(proj):
    edit(proj, "strategy.md", "→ F-2", "→ F-9")
    edit(proj, "options.md", "· close ·", "· other ·")


def _set_state(proj, text):
    (project_path(proj) / "state.yaml").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("st", [
    "step: null\ndone: {}\n", "done: {}\n", "step: {name: strategy}\ndone: {}\n", "step: {n: -1}\ndone: {}\n",
    "step: {n: 3}\ndone: {}\n", "step: {n: 0}\ndone: {}\n", "step: {n: 4}\ndone: {}\n", "step: {n: '5'}\ndone: {}\n",
    "step: {n: abc}\ndone: {}\n", "step: 5\ndone: {}\n", "step: [5]\ndone: {}\n", "step: {n: 5, name: x}\ndone: {}\n",
])
def test_filled_documents_never_skipped_whatever_step(proj, monkeypatch, capsys, st):
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])
    _break_strategy(proj)
    _set_state(proj, st)
    assert rc(["-p", proj]) == 1
    assert "пропущено" not in capsys.readouterr().out


@pytest.mark.parametrize("st", [": : [\n", "- 1\n- 2\n", "step: {n: 5\n"])
def test_broken_state_yaml_no_traceback_full_checks(proj, monkeypatch, capsys, st):
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])
    _break_strategy(proj)
    _set_state(proj, st)
    assert rc(["-p", proj]) == 1
    out = capsys.readouterr().out
    assert "state.yaml не читается" in out and "пропущено" not in out


def test_missing_state_file_full_checks(proj, monkeypatch):
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])
    _break_strategy(proj)
    (project_path(proj) / "state.yaml").unlink()
    assert rc(["-p", proj]) == 1


def test_empty_template_at_step2_skips_and_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])
    shutil.copytree(TEMPLATE, tmp_path / "projects" / "fresh")
    (project_path("fresh") / "state.yaml").write_text("step: {n: 2, name: x}\ndone: {}\n", encoding="utf-8")
    assert check.main(["-p", "fresh"]) == 0
    assert "пропущено: проверки 5, 6, 7, 8, 9, 10" in capsys.readouterr().out


def test_options_started_not_skipped_at_early_step(proj, monkeypatch):
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])
    p = project_path(proj) / "strategy.md"
    p.write_text((TEMPLATE / "strategy.md").read_text(encoding="utf-8"), encoding="utf-8")  # стратегии нет, варианты есть
    edit(proj, "options.md", "· close ·", "· other ·")
    _set_state(proj, "step: {n: 3}\ndone: {}\n")
    assert rc(["-p", proj]) == 1


@pytest.mark.parametrize("line", ["- «Перенос» → F-2, F-9", "- «A» → F-1; «B» → F-9", "- «Перенос» → F-1 и F-9"])
def test_promise_all_feature_ids_checked(proj, line):
    edit(proj, "strategy.md", "- «Перенос номера в один шаг» → F-2", line)
    assert any("F-9" in f.msg for f in fails(check_promises_static(proj)))


@pytest.mark.parametrize("line", ["«Безлимит навсегда» — наше главное обещание.", "| «Перенос» | F-9 |", "Обещаем F-9 всем."])
def test_promise_like_lines_must_match_format(proj, line):
    edit(proj, "strategy.md", "- «Перенос номера в один шаг» → F-2", line)
    assert fails(check_promises_static(proj))


def test_numbered_line_without_ref_is_not_thesis(proj):
    set_thesis(proj, "- Т1: Барьер — активация [C-002].\n\n1. Согласовать план с командой.\n2. Запустить опрос.")
    res = check_basis(proj)
    assert not fails(res) and "тезисов 1" in res[0].msg
    set_thesis(proj, "- Т1: Барьер — активация без ссылки.")
    assert fails(check_basis(proj))


def _exhaust(proj):
    edit(proj, "strategy.md", "Абонент перед сменой телефона.\n", "")
    for _ in range(3):
        check.main(["-p", proj, "--only", "6"])


def test_resolve_clears_waiting_and_counter(proj):
    _exhaust(proj)
    assert "--resolve" in state.load(proj)["waiting"]["question"] and "--resolve" in report(proj)
    assert check.main(["-p", proj, "--resolve", "переписал раздел", "--minutes", "5", "--only", "6"]) == 1
    st = state.load(proj)
    assert st["waiting"] is None and st["human"][-1]["minutes"] == 5 and st["check_fails"]["count"] == 1
    log = [json.loads(x) for x in (project_path(proj) / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(e["kind"] == "human" and e.get("minutes") == 5 for e in log)


def test_resolve_without_waiting_or_minutes_exit_3(proj):
    assert rc(["-p", proj, "--resolve", "x", "--minutes", "1"]) == 3
    _exhaust(proj)
    assert rc(["-p", proj, "--resolve", "x"]) == 3


def test_help_mentions_resolve(capsys):
    with pytest.raises(SystemExit):
        check.main(["--help"])
    assert "--resolve" in capsys.readouterr().out


def test_waiting_as_string_from_playbook_does_not_crash(proj, capsys):
    """playbooks пишут `waiting: "точка 3"` строкой: check.py не падает, лимит итераций работает."""
    st = state.load(proj)
    st["waiting"] = "точка 3"
    st["step"] = {"n": 5, "name": "strategy"}
    state.save(proj, st)
    assert rc(["-p", proj, "--only", "1,2,3,4,5,6,7,8,9,10"]) == 0
    edit(proj, "strategy.md", "→ F-1", "→ F-9")
    for _ in range(3):
        assert rc(["-p", proj, "--only", "7"]) == 1
    assert state.load(proj)["waiting"]["point"] == "check"


@pytest.mark.parametrize("n", [0, 3, 4])
def test_freeform_strategy_is_not_skipped_on_early_step(proj, capsys, monkeypatch, n):
    """Стратегия не по шаблону (свои заголовки) на раннем шаге не пропускается и не получает код 0."""
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])  # п.11 проверяется отдельно
    st = state.load(proj)
    st["step"] = {"n": n, "name": "x"}
    state.save(proj, st)
    (project_path(proj) / "strategy.md").write_text("# Стратегия\n\n## 1. Что делаем\nЗапускаем eSIM [C-001].\n", encoding="utf-8")
    assert rc(["-p", proj]) == 1
    assert "пропущено: проверки 6" not in capsys.readouterr().out


def test_text_under_non_leaf_heading_is_not_skipped(proj, capsys, monkeypatch):
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])
    st = state.load(proj)
    st["step"] = {"n": 4, "name": "options"}
    state.save(proj, st)
    (project_path(proj) / "strategy.md").write_text("## Продуктовая стратегия\nВесь текст здесь, без подразделов.\n", encoding="utf-8")
    assert rc(["-p", proj]) == 1


def test_freeform_options_are_not_skipped_on_early_step(proj, capsys, monkeypatch):
    monkeypatch.setattr(check, "check_lock", lambda root=None: [])
    st = state.load(proj)
    st["step"] = {"n": 3, "name": "research"}
    state.save(proj, st)
    (project_path(proj) / "options.md").write_text("# Варианты\n\n### Вариант 1\nОставить как есть.\n", encoding="utf-8")
    assert rc(["-p", proj]) == 1
