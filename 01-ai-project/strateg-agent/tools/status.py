# Статус проекта и учёт стоимости по 5 статьям (У2, У5, У12, У14): без него не видно шаг, ожидание человека, ₽ и деградации. Читает журнал устойчиво: битые и неизвестные записи не роняют вывод.
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from tools import lock, review as review_mod, state  # noqa: E402
from tools.common import ROOT, current_slug, project_path, projects_dir, read_text, read_yaml, setup_stdio  # noqa: E402

PRICES_PATH: Path = ROOT / "config" / "prices.yaml"
RED, YELLOW = "[КРАСНАЯ]", "[ЖЁЛТАЯ]"
YANDEX_CATEGORIES = {None, "", "yandex", "lite", "pro"}  # остальные категории llm-вызовов идут в «повторы и сбои» (У2)
RED_FLAGS = {"env-model", "lock"}
STEP_PLAYBOOKS = {1: "playbooks/1-frame.md", 2: "playbooks/2-collect.md", 3: "playbooks/3-research.md",
                  4: "playbooks/4-options.md", 5: "playbooks/5-strategy.md", 6: "playbooks/6-after-decision.md"}
HOOK_MAX_LINES = 25


def _num(v) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if math.isfinite(float(v)) else None


def _prices() -> dict:
    try:
        d = read_yaml(PRICES_PATH)
    except (OSError, ValueError, Exception):  # noqa: BLE001 — битый yaml не должен ронять статус
        return {}
    return d if isinstance(d, dict) else {}


def _journal(slug) -> tuple[list[dict], int]:
    """Журнал построчно: битые строки и не-объекты пропускаются и считаются."""
    p = project_path(slug) / "log.jsonl"
    if not p.is_file():
        return [], 0
    events, bad = [], 0
    for line in read_text(p).splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(obj, dict):
            events.append(obj)
        else:
            bad += 1
    return events, bad


def _scan(slug) -> dict:
    pr = _prices()
    rate = _num((pr.get("usd_rub") or {}).get("value")) if isinstance(pr.get("usd_rub"), dict) else None
    hour = _num(pr.get("human_rub_per_hour"))
    search_cfg = pr.get("search") if isinstance(pr.get("search"), dict) else {}
    events, bad = _journal(slug)
    s = {"yandex": 0.0, "env_model": 0.0, "search": 0.0, "retries": 0.0, "human": 0.0, "minutes": 0.0,
         "unknown_price": 0, "unknown_rate": False, "unknown_search": 0, "bad_lines": bad,
         "retry_calls": 0, "repairs": 0, "escalations": 0, "errors": 0, "bypasses": 0, "degraded": [],
         "no_human_rate": False}
    for e in events:
        k = e.get("kind")
        if k == "llm":
            rub = _num(e.get("rub"))
            if rub is None:
                s["unknown_price"] += 1
                rub = 0.0
            if e.get("category") in YANDEX_CATEGORIES:
                s["yandex"] += rub
            else:
                s["retries"] += rub
                s["retry_calls"] += 1
        elif k == "repair":
            s["repairs"] += 1
        elif k == "escalation":
            s["escalations"] += 1  # деньги эскалации уже в её llm-событии (категория retry)
        elif k == "error":
            s["errors"] += 1
        elif k == "model":
            usd = _num(e.get("usd")) or 0.0
            if rate is None:
                s["unknown_rate"] = True
            else:
                s["env_model"] += usd * rate
        elif k == "search":
            eng = e.get("engine")
            if eng == "cursor":
                continue  # входит в подписку
            if eng == "claude":
                per = _num(search_cfg.get("claude_usd_per_1k"))
                per = per * rate if per is not None and rate is not None else None
            else:  # opencode/other: считаем по прайсу поиска AI Studio
                per = _num(search_cfg.get("yandex_rub_per_1k"))
            if per is None:
                s["unknown_search"] += 1
            else:
                s["search"] += per / 1000
        elif k == "human":
            m = _num(e.get("minutes")) or 0.0
            s["minutes"] += m
            if hour is None:
                s["no_human_rate"] = True
            else:
                s["human"] += m / 60 * hour
            if "обход" in str(e.get("what") or "").lower():  # ручной обход помечается словом «обход» в описании
                s["bypasses"] += 1
        elif k == "bypass":
            s["bypasses"] += 1
        elif k == "degraded":
            s["degraded"].append((str(e.get("flag") or "?"), str(e.get("note") or "")))
    return s


def costs(slug=None) -> dict:
    """₽ по 5 статьям (yandex, env_model, search, retries, human), total и minutes (минуты человека)."""
    s = _scan(slug)
    out = {k: round(s[k], 4) for k in ("yandex", "env_model", "search", "retries", "human")}
    out["total"] = round(sum(out.values()), 4)
    out["minutes"] = round(s["minutes"], 2)
    return out


def _one_line(text, limit=160) -> str:
    t = " ".join(str(text).split())
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _rub(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def _degraded_lines(slug, s: dict, st: dict) -> tuple[list[str], list[str]]:
    reds, yellows = [], []
    seen = set()
    for flag, note in [(str(d.get("flag") or "?"), str(d.get("note") or "")) for d in st.get("degraded") or []
                       if isinstance(d, dict)] + s["degraded"]:
        if (flag, note) in seen:
            continue
        seen.add((flag, note))
        line = _one_line(f"{flag}: {note}" if note else flag)
        (reds if flag in RED_FLAGS else yellows).append(f"{RED if flag in RED_FLAGS else YELLOW} {line}")
    if any(f == "env-model" for f, _ in seen):
        yellows.append(f"{YELLOW} критик — модель среды в чистом контексте, независимость только за счёт чистого контекста")
    main_f, crit_f = os.environ.get("MAIN_MODEL_FAMILY", "").strip(), os.environ.get("CRITIC_MODEL_FAMILY", "").strip()
    if not main_f or not crit_f:
        from tools import llm
        llm.load_env()
        main_f, crit_f = os.environ.get("MAIN_MODEL_FAMILY", "").strip(), os.environ.get("CRITIC_MODEL_FAMILY", "").strip()
    if main_f and main_f == crit_f:
        yellows.append(f"{YELLOW} критик того же семейства, независимость только за счёт чистого контекста")
    if s["unknown_price"]:
        yellows.append(f"{YELLOW} цена неизвестна у {s['unknown_price']} вызовов модели: ₽ занижены (заполните config/prices.yaml)")
    if s["unknown_rate"]:
        yellows.append(f"{YELLOW} цена неизвестна: нет курса usd_rub в config/prices.yaml, расход модели среды не переведён в ₽")
    if s["unknown_search"]:
        yellows.append(f"{YELLOW} цена неизвестна у {s['unknown_search']} поисковых запросов: ₽ занижены")
    if s["no_human_rate"]:
        yellows.append(f"{YELLOW} цена неизвестна: нет human_rub_per_hour в config/prices.yaml, время человека не переведено в ₽")
    step_n = (st.get("step") or {}).get("n") if isinstance(st.get("step"), dict) else 0
    if isinstance(step_n, int) and step_n >= 2 and not s["env_model"]:
        yellows.append(f"{YELLOW} расход модели среды не записан: статья 0 ₽ занижена. Что сделать: `/cost` в Claude Code (или счётчик среды) → "
                       f"`python tools/log.py model <usd> --manual`")
    if s["errors"]:
        yellows.append(f"{YELLOW} сбоев вызова модели: {s['errors']} (см. log.jsonl, kind=error)")
    if s["bad_lines"]:
        yellows.append(f"{YELLOW} в log.jsonl нечитаемых строк: {s['bad_lines']} (пропущены)")
    return reds, yellows


def _next_action(slug, st: dict, lock_problems: list[str]) -> str:
    if lock_problems:
        return "python tools/lock.py --verify  (правила изменены: разберитесь до работы)"
    point, question = _waiting_parts(st.get("waiting"))
    if point or question:
        return (f'ответить человеку, затем `python tools/state.py resolve "{point or "точка N"}" '
                f'--summary "<что решил человек>" --minutes <мин>`')
    step = st.get("step") if isinstance(st.get("step"), dict) else {}
    n = step.get("n") if isinstance(step.get("n"), int) else 0
    if n == 0:
        return f"прочитай {STEP_PLAYBOOKS[1]} и начни шаг 1"
    if n in STEP_PLAYBOOKS:
        return f"открой {STEP_PLAYBOOKS[n]} и продолжи шаг"
    return "python tools/status.py"


def _waiting_parts(waiting) -> tuple[str, str]:
    """(точка, вопрос): ожидание бывает словарём {point, question} или строкой «точка 1» (так велят playbooks)."""
    if isinstance(waiting, dict):
        return str(waiting.get("point") or "").strip(), str(waiting.get("question") or "").strip()
    if isinstance(waiting, str) and waiting.strip():
        return waiting.strip(), ""
    return "", ""


def _dates_lines() -> list[str]:
    as_of = _prices().get("as_of")
    upd = None
    try:
        upd = lock.last_update(ROOT)
    except Exception:  # noqa: BLE001 — битый rules.lock не должен ронять статус
        pass
    when = upd.get("updated_at") if isinstance(upd, dict) else None
    why = upd.get("reason") if isinstance(upd, dict) else None
    return [f"Цены (config/prices.yaml): на {as_of if as_of else 'неизвестно'}",
            "Правила обновлены (lock.py --update): " + (_one_line(f"{when}" + (f" — {why}" if why else ""), 200)
                                                         if when else "неизвестно")]


def render(slug=None, hook: bool = False) -> str:
    lock_problems = lock.verify(ROOT)
    lock_line = "rules.lock: OK" if not lock_problems else (
        f"{RED} rules.lock: {_one_line('; '.join(lock_problems), 300)}. Что сделать: `python tools/lock.py --verify`")
    if slug is None:
        slug = current_slug()
    if slug is None or not (projects_dir() / slug).is_dir():
        return "\n".join([
            "Проект: не выбран",
            lock_line,
            "Следующее действие: python tools/project.py new <имя>",
        ])
    st, st_err = state.read_checked(slug)
    if st_err:
        return chr(10).join([f"Проект: {slug}", f"{RED} {st_err}", lock_line,
                          "Следующее действие: исправь projects/" + str(slug) + "/state.yaml"])
    s = _scan(slug)
    c = costs(slug)
    reds, yellows = _degraded_lines(slug, s, st)
    review_lines = review_mod.review(slug)
    step = st.get("step") if isinstance(st.get("step"), dict) else {}
    waiting = st.get("waiting")
    point, question = _waiting_parts(waiting)
    wait_txt = (_one_line(f"{point}: {question}" if point and question else (point or question), 200)
                if point or question else "ничего")
    done = len(st.get("done") or {})
    nxt = f"Следующее действие: {_next_action(slug, st, lock_problems)}"
    head = f"Проект: {slug} · шаг {step.get('n', 0)} {step.get('name', '')} · сделано действий: {done}"
    cost_line = (f"Стоимость: итого {_rub(c['total'])} · человек {c['minutes']:g} мин")
    if hook:
        out = [head, f"Ждёт от человека: {wait_txt}", cost_line]
        if lock_problems:
            out.append(lock_line)
        out += reds[:8]
        if len(reds) > 8:
            out.append(f"{RED} …и ещё {len(reds) - 8}")
        if yellows:
            out.append(f"{YELLOW} замечаний: {len(yellows)}. Подробнее: `python tools/status.py`")
        return "\n".join(_one_line(x, 300) for x in out[:HOOK_MAX_LINES - 1] + [nxt])
    out = [
        head,
        f"Ждёт от человека: {wait_txt}",
        "Стоимость по 5 статьям:",
        f"  Yandex (успешные первые вызовы): {_rub(c['yandex'])}",
        f"  Модель среды: {_rub(c['env_model'])}",
        f"  Поиск: {_rub(c['search'])}",
        f"  Повторы и сбои: {_rub(c['retries'])} (ретраев {s['retry_calls']}, ремонтов {s['repairs']}, эскалаций {s['escalations']})",
        f"  Человек: {_rub(c['human'])} ({c['minutes']:g} мин)",
        f"  Итого: {_rub(c['total'])} · минуты человека: {c['minutes']:g}",
        f"Ручных обходов: {s['bypasses']}",
        lock_line,
        *_dates_lines(),
        "Деградации:",
    ]
    dl = reds + yellows
    out += [f"  {x}" for x in dl[:15]] if dl else ["  нет"]
    if len(dl) > 15:
        out.append(f"  …и ещё {len(dl) - 15}")
    out.append("Пересмотр:")
    out += [f"  {_one_line(x, 200)}" for x in review_lines] if review_lines else ["  нет"]
    out.append(nxt)
    return "\n".join(out)


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(
        description="Статус проекта: шаг, что ждёт от человека, ₽ по 5 статьям, ручные обходы, сверка rules.lock, деградации, пересмотр.")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    ap.add_argument("--hook", action="store_true", help="короткий вывод (до 25 строк) для хука SessionStart; не падает при ошибках")
    a = ap.parse_args(argv)
    if a.hook:
        try:
            print(render(a.project, hook=True))
        except BaseException as e:  # noqa: BLE001 — хук не должен ломать старт сессии
            if isinstance(e, KeyboardInterrupt):
                raise
            print(f"Статус недоступен ({type(e).__name__}). Что сделать: `python tools/status.py`.")
        return 0
    print(render(a.project))
    return 0


if __name__ == "__main__":
    sys.exit(main())
