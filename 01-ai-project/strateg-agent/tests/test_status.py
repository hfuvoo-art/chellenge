# Тесты status.py: проверяют блоки статуса, учёт стоимости по 5 статьям без двойного счёта и устойчивость вывода; без них старт сессии врёт про деньги или падает в консоли Windows.
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tools import log, state, status
from tools.common import ROOT


@pytest.fixture
def prices(tmp_path, monkeypatch):
    p = tmp_path / "prices.yaml"
    p.write_text(yaml.safe_dump({
        "usd_rub": {"value": 80.0},
        "search": {"claude_usd_per_1k": 10, "yandex_rub_per_1k": 915, "cursor": "included"},
        "human_rub_per_hour": 1200,
    }), encoding="utf-8")
    monkeypatch.setattr(status, "PRICES_PATH", p)
    monkeypatch.setattr(status.lock, "verify", lambda root: [])
    for k in ("MAIN_MODEL_FAMILY", "CRITIC_MODEL_FAMILY"):
        monkeypatch.delenv(k, raising=False)
    return p


@pytest.fixture
def proj(tmp_project, prices):
    return tmp_project


def _llm(slug, category, rub, **kw):
    log.event(slug, "llm", role="extract", model="m", usage={}, rub=rub, category=category, attempts=1, **kw)


def test_status_has_all_blocks(proj):
    state.set_step(proj, 3, "research")
    state.wait_human(proj, "Точка 1", "Какой рынок?")
    out = status.render(proj)
    for needle in ("Проект:", "Ждёт от человека:", "Стоимость", "Ручных обходов:", "rules.lock: OK",
                   "Деградации:", "Пересмотр:", "Следующее действие:"):
        assert needle in out, needle
    assert "Какой рынок?" in out and "research" in out


def test_costs_five_articles_no_double_count(proj):
    _llm(proj, "yandex", 1.0)
    _llm(proj, "yandex", 2.0)
    _llm(proj, "retry", 0.5)          # ретрай/ремонт/эскалация идут только в «повторы» (У2)
    log.event(proj, "escalation", rub=99, to="pro")  # событие эскалации само денег не добавляет
    log.event(proj, "model", usd=0.5, manual=True)    # 0,5 × 80 = 40 ₽
    log.event(proj, "search", query="q", engine="claude")  # 10/1000 × 80 = 0,8 ₽
    log.event(proj, "search", query="q2", engine="cursor")  # входит в подписку
    log.event(proj, "human", minutes=30, what="правки")      # 30 мин × 1200/60 = 600 ₽
    state.resolve_human(proj, "Точка 1", "ок", 6)             # 6 мин = 120 ₽
    c = status.costs(proj)
    assert c["yandex"] == pytest.approx(3.0)
    assert c["retries"] == pytest.approx(0.5)
    assert c["env_model"] == pytest.approx(40.0)
    assert c["search"] == pytest.approx(0.8)
    assert c["human"] == pytest.approx(720.0)
    assert c["minutes"] == pytest.approx(36.0)
    assert c["total"] == pytest.approx(3.0 + 0.5 + 40.0 + 0.8 + 720.0)


def test_status_ascii_console(proj):
    _llm(proj, "yandex", 1.5)
    log.event(proj, "degraded", flag="env-model", note="ответ модели среды")
    out = status.render(proj)
    assert not re.search(r"\x1b\[", out)
    assert all(ord(ch) < 0x2190 for ch in out), "эмодзи и спецсимволы не нужны"
    assert {ch for ch in out if ord(ch) > 127 and ch.encode("cp1251", "ignore") == b""} <= {"₽"}
    env = {**os.environ, "STRATEG_PROJECTS_DIR": os.environ["STRATEG_PROJECTS_DIR"]}
    for enc in ("cp1251", "ascii"):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "status.py"), "-p", proj],
                           capture_output=True, env={**env, "PYTHONIOENCODING": enc}, timeout=60)
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
        assert b"Traceback" not in r.stderr


def test_red_line_when_lock_broken(proj, monkeypatch):
    monkeypatch.setattr(status.lock, "verify", lambda root: ["изменён: rules/evidence.md"])
    out = status.render(proj)
    assert "[КРАСНАЯ] rules.lock" in out and "rules/evidence.md" in out
    assert "rules.lock: OK" not in out
    assert "lock.py --verify" in out.split("Следующее действие:")[1]


def test_yellow_when_price_unknown_or_same_family(proj, monkeypatch):
    assert "[ЖЁЛТАЯ]" not in status.render(proj)
    _llm(proj, "yandex", None)
    out = status.render(proj)
    assert "[ЖЁЛТАЯ]" in out and "цена" in out
    monkeypatch.setenv("MAIN_MODEL_FAMILY", "yandexgpt")
    monkeypatch.setenv("CRITIC_MODEL_FAMILY", "yandexgpt")
    out = status.render(proj)
    assert "критик того же семейства, независимость только за счёт чистого контекста" in out


def test_env_model_degradation_red(proj):
    state.add_degraded(proj, "env-model", "извлечение моделью среды")
    out = status.render(proj)
    assert "[КРАСНАЯ]" in out and "env-model" in out


def test_hook_mode_short(proj):
    state.wait_human(proj, "Точка 1", "Вопрос " * 50)
    for i in range(40):
        state.add_degraded(proj, "env-model", f"заметка {i}")
        log.event(proj, "degraded", flag="x", note=str(i))
    out = status.render(proj, hook=True)
    assert len(out.splitlines()) <= 25
    assert "Следующее действие:" in out


def test_unknown_and_broken_journal_lines_do_not_crash(proj):
    path = Path(os.environ["STRATEG_PROJECTS_DIR"]) / proj / "log.jsonl"
    path.write_text('{"kind": "escalation", "from": "lite"}\n{"kind": "zzz"}\n[1,2]\n{"kind": "llm", "rub": "x"}\n'
                    '{"kind": "model", "usd": "?"}\n{"ts": "обрыв', encoding="utf-8")
    out = status.render(proj)
    assert "Стоимость" in out
    c = status.costs(proj)
    assert math.isfinite(c["total"]) and c["total"] == 0
    assert "nan" not in out.lower() and "inf" not in out.lower().replace("информ", "")
    assert "[ЖЁЛТАЯ]" in out and "цена" in out


def test_manual_bypass_count(proj):
    log.event(proj, "human", minutes=5, what="правки")
    assert "Ручных обходов: 0" in status.render(proj)
    log.event(proj, "human", minutes=5, what="Ручной ОБХОД: PDF")
    log.event(proj, "bypass", what="x")
    assert "Ручных обходов: 2" in status.render(proj)


def test_hook_lines_capped_and_next_kept(proj):
    state.wait_human(proj, "Т", "я" * 5000)
    out = status.render(proj, hook=True)
    assert all(len(x) <= 300 for x in out.splitlines())
    assert out.splitlines()[-1].startswith("Следующее действие:")


def test_no_project_gives_next_step(tmp_path, monkeypatch, prices):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "empty"))
    out = status.render(None)
    assert "project.py new" in out


def test_help_in_russian():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "status.py"), "--help"], capture_output=True, timeout=60)
    assert r.returncode == 0 and re.search("[а-яё]", r.stdout.decode("utf-8", "replace").lower())


def _set_waiting(slug, value):
    st = state.load(slug)
    st["waiting"] = value
    state.save(slug, st)


def test_string_waiting_shown_like_dict(proj):
    _set_waiting(proj, "точка 1")
    out = status.render(proj)
    assert "Ждёт от человека: точка 1" in out
    nxt = out.split("Следующее действие:")[1]
    assert "state.py resolve" in nxt and "точка 1" in nxt
    assert "Ждёт от человека: точка 1" in status.render(proj, hook=True)


def test_dict_waiting_next_action_is_resolve(proj):
    state.wait_human(proj, "точка 2", "Какой вариант?")
    out = status.render(proj)
    assert "точка 2: Какой вариант?" in out
    assert 'state.py resolve "точка 2"' in out.split("Следующее действие:")[1]


def test_step0_with_project_points_to_playbook(proj):
    out = status.render(proj)
    nxt = out.split("Следующее действие:")[1]
    assert "playbooks/1-frame.md" in nxt and "project.py new" not in nxt


def test_next_action_by_step_opens_playbook(proj):
    state.set_step(proj, 4, "options")
    assert "playbooks/4-options.md" in status.render(proj).split("Следующее действие:")[1]


def test_prices_and_lock_dates_in_full_status_not_hook(proj, monkeypatch):
    p = status.PRICES_PATH
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    d["as_of"] = "2026-11-09"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    monkeypatch.setattr(status.lock, "last_update",
                        lambda root: {"updated_at": "2026-11-12T10:00:00+00:00", "reason": "правка AGENTS.md"})
    out = status.render(proj)
    assert "2026-11-09" in out and "2026-11-12T10:00:00" in out and "правка AGENTS.md" in out
    hook = status.render(proj, hook=True)
    assert "2026-11-09" not in hook and "Цены" not in hook


def test_dates_unknown_when_missing(proj, monkeypatch):
    monkeypatch.setattr(status.lock, "last_update", lambda root: None)
    out = status.render(proj)
    assert "Цены (config/prices.yaml): на неизвестно" in out
    assert "Правила обновлены (lock.py --update): неизвестно" in out


def test_state_cli_flow_costs_minutes_once(proj):
    assert state.main(["-p", proj, "step", "1", "frame"]) == 0
    assert state.main(["-p", proj, "wait", "точка 1", "Подтверждаете?"]) == 0
    assert "точка 1: Подтверждаете?" in status.render(proj)
    assert state.main(["-p", proj, "resolve", "точка 1", "--summary", "ок", "--minutes", "6"]) == 0
    out = status.render(proj)
    assert "Ждёт от человека: ничего" in out
    assert status.costs(proj)["minutes"] == pytest.approx(6.0)
    assert status.costs(proj)["human"] == pytest.approx(120.0)


@pytest.mark.parametrize("content", ["step: [unclosed\n  : :", "[1, 2]\n"])
def test_broken_state_yaml_red_line_not_traceback(proj, tmp_path, content):
    (tmp_path / "projects" / proj / "state.yaml").write_text(content, encoding="utf-8")
    out = status.render(proj)
    assert "[КРАСНАЯ]" in out and "state.yaml не читается" in out
    assert "Следующее действие:" in out
    assert "state.yaml не читается" in status.render(proj, hook=True) or "Статус" in status.render(proj, hook=True)
