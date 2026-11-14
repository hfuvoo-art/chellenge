# Тесты слепого сравнения: без них метки C-/F-/S- в ответе агента выдадут его судье, перемешивание не воспроизведётся, а кейсы инъекций перестанут помечаться при приёме.
import json
import re
from pathlib import Path

from evals import blind
from tools import ingest
from tools.common import project_path, read_yaml

CASES = Path(__file__).resolve().parent.parent / "evals" / "cases" / "injection"
AGENT = """# Стратегия

## Рекомендация
Запустить пилот в Турции [C-135], [C-133]. Функции F-1 и F-2 снимают риск [C-115, C-100].
Источник S-003 и S-004; решение D-2, вопрос Q1, вариант O3.
<!-- служебный комментарий -->
[SYNTHETIC] интервью.
"""
CHAT = "Рекомендую начать с Турции: eSIM дешевле роуминга (источник: сайт оператора)."
LABEL_RE = re.compile(r"\[C-|\bC-\d|\bF-\d|\bS-\d|\bD-\d|<!--|SYNTHETIC")


def test_blind_strips_ids_and_labels(tmp_path):
    a, c = tmp_path / "agent.md", tmp_path / "chat.md"
    a.write_text(AGENT, encoding="utf-8")
    c.write_text(CHAT, encoding="utf-8")
    out = tmp_path / "blind"
    blind.prepare(a, c, seed=1, out_dir=out)
    for name in ("A.txt", "B.txt"):
        text = (out / name).read_text(encoding="utf-8")
        assert not LABEL_RE.search(text), text
    joined = (out / "A.txt").read_text(encoding="utf-8") + (out / "B.txt").read_text(encoding="utf-8")
    assert "Запустить пилот в Турции" in joined and "eSIM дешевле роуминга" in joined  # смысл остался
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    assert set(key["map"].values()) == {"agent", "chat"} and key["seed"] == 1


def test_blind_shuffle_reproducible(tmp_path):
    a, c = tmp_path / "agent.md", tmp_path / "chat.md"
    a.write_text(AGENT, encoding="utf-8")
    c.write_text(CHAT, encoding="utf-8")

    def run(seed, name):
        out = tmp_path / name
        blind.prepare(a, c, seed=seed, out_dir=out)
        return json.loads((out / "key.json").read_text(encoding="utf-8"))["map"], (out / "A.txt").read_text(encoding="utf-8")

    assert run(7, "x1") == run(7, "x2")  # тот же seed — тот же порядок
    orders = {json.dumps(run(s, f"s{s}")[0], sort_keys=True) for s in range(12)}
    assert len(orders) == 2  # перемешивание реально меняет порядок


def test_injection_case_flagged_on_ingest(tmp_project):
    rt_project = tmp_project
    files = sorted(p for p in CASES.iterdir() if p.is_file() and p.suffix in (".md", ".csv", ".html"))
    assert len(files) >= 3
    for f in files:
        sid = ingest.ingest(rt_project, str(f), found_by="user")
        src = next(s for s in read_yaml(project_path(rt_project) / "sources.yaml")["sources"] if s["id"] == sid)
        assert src["suspicious"], f"{f.name}: инъекция не помечена"


def test_blind_keeps_dates_and_strips_paths(tmp_path):
    a, c = tmp_path / "agent.md", tmp_path / "chat.md"
    a.write_text("Пилот к 2027-Q2, оценка на Q4 2026. Расчёт: calc/market.md и methods/jtbd.md.\n", encoding="utf-8")
    c.write_text("ок", encoding="utf-8")
    blind.prepare(a, c, seed=3, out_dir=tmp_path / "o")
    text = (tmp_path / "o" / "A.txt").read_text(encoding="utf-8") + (tmp_path / "o" / "B.txt").read_text(encoding="utf-8")
    assert "2027-Q2" in text and "Q4 2026" in text
    assert "calc/" not in text and "methods/" not in text
