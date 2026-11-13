# Тесты panel.py: шаги, ожидание человека, источники, варианты, стоимость, экранирование, пустой и битый проект, консоль; без них панель может молча врать о статусе или исполнять чужой HTML.
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tools import panel, status
from tools.common import project_path

FIX = Path(__file__).parent / "fixtures" / "proj-ok"
TPL = Path(__file__).resolve().parent.parent / "projects" / "_template"
AGENT = Path(__file__).resolve().parent.parent


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    shutil.copytree(FIX, tmp_path / "projects" / "ok")
    return "ok"


def _set_state(slug, **kw):
    p = project_path(slug) / "state.yaml"
    st = yaml.safe_load(p.read_text(encoding="utf-8"))
    st.update(kw)
    p.write_text(yaml.safe_dump(st, allow_unicode=True), encoding="utf-8")


def test_panel_steps_and_current(proj):
    h = panel.render_panel(proj)
    assert "Постановка" in h and "Стратегия" in h and "После решения" in h
    assert 'class="cur">5. Стратегия' in h and 'class="done">1.' in h and 'class="next">6.' in h
    assert "default-src 'none'" in h and "<script" not in h.lower()


def test_panel_waiting_string_and_dict(proj):
    _set_state(proj, waiting="точка 2")
    assert "точка 2" in panel.render_panel(proj)
    _set_state(proj, waiting={"point": "точка 3", "question": "Принять стратегию?"})
    h = panel.render_panel(proj)
    assert "точка 3: Принять стратегию?" in h
    _set_state(proj, waiting=None)
    assert "ничего" in panel.render_panel(proj)


def test_panel_sources_options_cost(proj):
    h = panel.render_panel(proj)
    assert "Условный отчёт о рынке eSIM" in h and "S-001" in h
    assert "O3" in h and "Упростить активацию и перенос номера" in h
    assert "Стоимость" in h and "Итого" in h
    assert "Утверждения" in h


def test_panel_escapes_and_links(proj):
    p = project_path(proj) / "sources.yaml"
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    d["sources"][0]["title"] = "<script>alert(1)</script>"
    d["sources"][1]["url"] = "javascript:alert(1)"
    d["sources"][1]["suspicious"] = ["x"]
    p.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    h = panel.render_panel(proj)
    assert "<script>alert" not in h and "&lt;script&gt;" in h
    assert 'href="javascript:' not in h
    assert "подозрительное" in h


def test_panel_http_link_kept(proj):
    p = project_path(proj) / "sources.yaml"
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    d["sources"][0]["url"] = "https://example.com/a?b=1&c=2"
    p.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    assert 'href="https://example.com/a?b=1&amp;c=2"' in panel.render_panel(proj)


def test_panel_empty_template_project(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    shutil.copytree(TPL, tmp_path / "projects" / "new")
    h = panel.render_panel("new")
    assert "пока нет" in h and "ничего" in h
    assert panel.write_panel("new").name == "panel.html"


def test_panel_broken_files_do_not_crash(proj):
    d = project_path(proj)
    (d / "state.yaml").write_text("step: [unclosed\n", encoding="utf-8")
    (d / "claims.jsonl").write_text("{bad json\n", encoding="utf-8")
    h = panel.render_panel(proj)
    assert 'class="red"' in h and "state.yaml" in h and "claims.jsonl" in h


def test_panel_question_status_from_questions_md(proj):
    q = project_path(proj) / "questions.md"
    q.write_text(q.read_text(encoding="utf-8") + "\n## Итог\n- Q1 — **отвечен.** текст\n", encoding="utf-8")
    h = panel.render_panel(proj)
    assert 'class="tag">отвечен' in h


def test_write_panel_and_cli(proj, tmp_path):
    out = panel.write_panel(proj)
    assert out == project_path(proj) / "panel.html"
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")
    env = {**os.environ, "STRATEG_PROJECTS_DIR": str(tmp_path / "projects"), "PYTHONIOENCODING": "cp1251"}
    r = subprocess.run([sys.executable, "tools/panel.py", "--help"], cwd=AGENT, env=env, capture_output=True)
    assert r.returncode == 0
    assert "Панель проекта".encode("utf-8") in r.stdout or "Панель проекта".encode("cp1251") in r.stdout
    r = subprocess.run([sys.executable, "tools/panel.py", "-p", proj], cwd=AGENT, env=env, capture_output=True)
    assert r.returncode == 0 and b"panel.html" in r.stdout
    r = subprocess.run([sys.executable, "tools/panel.py", "-p", "nope"], cwd=AGENT, env=env, capture_output=True)
    assert r.returncode == 3


def test_template_has_no_phantom_option(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    shutil.copytree(TPL, tmp_path / "projects" / "new")
    h = panel.render_panel("new")
    assert "status_quo" not in h and "Название" not in h


def test_yellow_red_and_total_match_status(proj):
    _set_state(proj, degraded=[{"flag": "x", "note": "n"}, {"flag": "lock", "note": "m"}])
    h = panel.render_panel(proj)
    assert "[ЖЁЛТАЯ]" in h and "[КРАСНАЯ]" in h
    assert status._rub(status.costs(proj)["total"]).replace(" ", " ") in h or status._rub(status.costs(proj)["total"]) in h


def test_request_first_paragraph_trimmed(proj):
    b = project_path(proj) / "brief.md"
    b.write_text("# Бриф\n\n## Вопрос\nЗапрос дословно: «" + "А" * 400 + "»\n\nВторой абзац ВТОРОЙ\n\n## Цель\nx\n", encoding="utf-8")
    h = panel.render_panel(proj)
    assert "Запрос дословно" not in h and "ВТОРОЙ" not in h and "…" in h


def test_choice_first_paragraph_no_double(proj):
    o = project_path(proj) / "options.md"
    o.write_text(o.read_text(encoding="utf-8") + "\n## Выбор (точка 2)\nВыбрано: O3 быстро.\n\nПричина ПРИЧИНА\n", encoding="utf-8")
    h = panel.render_panel(proj)
    assert "Выбрано: Выбрано" not in h and "Выбрано.</b> O3 быстро" in h and "ПРИЧИНА" not in h


def test_broken_state_still_shows_cost_with_note(proj):
    (project_path(proj) / "state.yaml").write_text("step: [unclosed\n", encoding="utf-8")
    h = panel.render_panel(proj)
    assert "стоимость может быть неполной" in h and "Итого" in h


def test_sources_wrong_structure_is_red(proj):
    (project_path(proj) / "sources.yaml").write_text("- just\n- a list\n", encoding="utf-8")
    h = panel.render_panel(proj)
    assert 'class="red"' in h and "sources.yaml" in h


def test_bool_step_is_not_a_step(proj):
    _set_state(proj, step={"n": True, "name": "x"})
    assert 'class="cur"' not in panel.render_panel(proj)


def test_css_wraps_long_cells():
    assert "overflow-wrap:anywhere" in panel.CSS


def test_cli_write_error_exit_1(proj, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk")
    monkeypatch.setattr(panel, "write_text_atomic", boom)
    assert pytest.raises(SystemExit, panel.main, ["-p", proj]).value.code == 1
