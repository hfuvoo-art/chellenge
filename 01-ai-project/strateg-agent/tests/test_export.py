# Тесты export.py: сноски вместо [C-…], названия функций, метки гипотез, сводка и источники, экранирование, DOCX, консоль; без них читаемая стратегия может молча терять ссылки или исполнять чужой HTML.
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools import export as ex
from tools.common import project_path

FIX = Path(__file__).parent / "fixtures" / "proj-ok"
AGENT = Path(__file__).resolve().parent.parent


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    shutil.copytree(FIX, tmp_path / "projects" / "ok")
    return "ok"


def _html(slug, warns=None):
    return ex.export(slug, "html", warns).read_text(encoding="utf-8")


def _edit_claims(slug, fn):
    p = project_path(slug) / "claims.jsonl"
    items = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    fn(items)
    p.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")


def test_export_replaces_ids_with_footnotes(proj):
    h = _html(proj)
    assert "[C-002]" not in h and "[C-001]" not in h
    assert 'href="#fn1"' in h and 'id="fn1"' in h
    assert "Из 40 опрошенных 18 человек назвали сложность активации главным барьером." in h  # цитата
    assert "Условный отчёт о рынке eSIM" in h and "2026-10-01" in h  # источник и as_of
    assert "¶2" in h  # локатор
    # F-n -> название и статус
    assert "Подключение eSIM по QR-коду без визита в салон" in h and "есть" in h
    assert "планируется с 2027-Q1" in h
    assert "→ F-2" not in h


def test_export_marks_hypotheses_and_synthetic(proj):
    def fn(items):
        items.append({"text": "Спрос вырастет вдвое", "type": "forecast", "extracted_by": "agent:claude", "question": ["Q1"],
                      "id": "C-005", "status": "active", "supersedes": None})
        items.append({"text": "Допущение о затратах", "type": "hypothesis", "extracted_by": "agent:claude", "question": ["Q1"],
                      "id": "C-006", "status": "active", "supersedes": None})
    _edit_claims(proj, fn)
    p = project_path(proj) / "strategy.md"
    p.write_text(p.read_text(encoding="utf-8").replace("Затраты на доработку", "Затраты [C-006] на доработку [C-005]"), encoding="utf-8")
    h = _html(proj)
    assert 'class="label">синтетика' in h  # C-003 в тезисе Т2
    assert 'class="label">гипотеза' in h
    assert 'class="label">прогноз' in h


def test_export_has_sources_and_summary(proj):
    h = _html(proj)
    i_sum = h.index("Решение за 1 минуту")
    assert i_sum < h.index("Продуктовая стратегия")
    assert "Упростить активацию eSIM до конца 2027 года" in h[i_sum:h.index("Продуктовая стратегия")]
    j = h.rindex("<h2>Источники</h2>")
    assert j > h.index("Сноски")
    tail = h[j:]
    assert "S-001" in tail and "S-002" in tail and "Синтетическое интервью R-1" in tail


def test_export_unknown_and_retracted_claims_are_flagged(proj):
    p = project_path(proj) / "strategy.md"
    p.write_text(p.read_text(encoding="utf-8").replace("[C-001]", "[C-999]").replace("[C-002]", "[C-004]", 1), encoding="utf-8")
    _edit_claims(proj, lambda items: items[3].update(status="retracted"))
    warns = []
    h = _html(proj, warns)
    assert "C-999: нет в реестре" in h and "C-004: отозвано" in h
    assert any("C-999" in w for w in warns) and any("C-004" in w for w in warns)


def test_export_escapes_html_in_source_data(proj):
    _edit_claims(proj, lambda items: items[0].update(quote="<script>alert(1)</script> & \"x\"", locator="<b>¶1</b>"))
    h = _html(proj)
    assert "<script>alert" not in h and "&lt;script&gt;alert(1)&lt;/script&gt;" in h
    assert "<b>¶1</b>" not in h
    assert "http-equiv=\"Content-Security-Policy\"" in h
    assert "http://" not in h.replace("http-equiv", "") and "https://" not in h  # без внешних ресурсов


def test_export_docx(proj):
    from docx import Document
    out = ex.export(proj, "docx")
    assert out.name == "strategy.docx" and out.parent.name == "export"
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "Решение за 1 минуту" in text and "Упростить активацию" in text
    assert "[C-002]" not in text and "планируется с 2027-Q1" in text and "(синтетика)" in text
    assert "Условный отчёт о рынке eSIM" in text


def test_export_errors(proj, tmp_path):
    with pytest.raises(ex.ExportError):
        ex.export(proj, "pdf")
    (project_path(proj) / "strategy.md").unlink()
    with pytest.raises(ex.ExportError, match="strategy.md"):
        ex.export(proj, "html")


def test_cli_cyrillic_path_ascii_console(tmp_path):
    root = tmp_path / "проекты с пробелом"
    shutil.copytree(FIX, root / "ok")
    env = {**os.environ, "STRATEG_PROJECTS_DIR": str(root), "PYTHONIOENCODING": "ascii"}
    r = subprocess.run([sys.executable, str(AGENT / "tools" / "export.py"), "-p", "ok"], capture_output=True, env=env, cwd=AGENT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert (root / "ok" / "export" / "strategy.html").is_file()
    r = subprocess.run([sys.executable, str(AGENT / "tools" / "export.py"), "-p", "net"], capture_output=True, env=env, cwd=AGENT)
    assert r.returncode == 3
    (root / "ok" / "strategy.md").unlink()
    r = subprocess.run([sys.executable, str(AGENT / "tools" / "export.py"), "-p", "ok"], capture_output=True, env=env, cwd=AGENT)
    assert r.returncode == 1 and "strategy.md" in r.stderr.decode("utf-8", "replace")
