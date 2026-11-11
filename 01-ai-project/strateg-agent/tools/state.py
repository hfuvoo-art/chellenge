# Состояние проекта (state.yaml): шаг, выполненные action_id, ожидание человека; CLI step/wait/resolve/show вместо ручной правки YAML. Без него повторный запуск после обрыва дублирует работу, а точки человека не попадают в state.yaml и статус.
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.common import now_iso, project_path, read_yaml, setup_stdio, sha256_text, write_yaml_atomic  # noqa: E402
from tools.log import event  # noqa: E402

STEP_NAMES = {1: "frame", 2: "collect", 3: "research", 4: "options", 5: "strategy", 6: "after-decision"}
_DEFAULT = {"step": {"n": 0, "name": "not-started"}, "done": {}, "waiting": None, "human": [], "degraded": []}


def load(slug: str | None) -> dict:
    p = project_path(slug) / "state.yaml"
    st = (read_yaml(p) if p.is_file() else None) or {}
    for k, v in _DEFAULT.items():
        if st.get(k) is None and k != "waiting":
            st[k] = copy.deepcopy(v)
    st.setdefault("waiting", None)
    return st


def save(slug: str | None, st: dict) -> None:
    write_yaml_atomic(project_path(slug) / "state.yaml", st)


def action_id(step: str, unit: str, payload) -> str:
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f"{step}:{unit}:{sha256_text(payload)[:12]}"


def is_done(slug: str | None, aid: str) -> bool:
    return aid in load(slug)["done"]


def mark_done(slug: str | None, aid: str, meta: dict | None = None) -> None:
    st = load(slug)
    if aid in st["done"]:
        return
    st["done"][aid] = {"at": now_iso(), **(meta or {})}
    save(slug, st)


def set_step(slug: str | None, n: int, name: str) -> None:
    st = load(slug)
    st["step"] = {"n": n, "name": name}
    save(slug, st)
    event(slug, "step", n=n, name=name)


def wait_human(slug: str | None, point: str, question: str) -> None:
    st = load(slug)
    st["waiting"] = {"point": point, "question": question, "since": now_iso()}
    save(slug, st)
    event(slug, "wait_human", point=point, question=question)


def resolve_human(slug: str | None, point: str, summary: str, minutes: float) -> None:
    st = load(slug)
    st["waiting"] = None
    st["human"].append({"point": point, "summary": summary, "minutes": minutes, "at": now_iso()})
    save(slug, st)
    event(slug, "human", point=point, summary=summary, minutes=minutes)


def add_degraded(slug: str | None, flag: str, note: str) -> None:
    st = load(slug)
    if not any(d.get("flag") == flag and d.get("note") == note for d in st["degraded"]):
        st["degraded"].append({"flag": flag, "note": note, "at": now_iso()})
        save(slug, st)
    event(slug, "degraded", flag=flag, note=note)


BROKEN_MSG = ("state.yaml не читается (битый YAML или не та структура). "
              "Что сделать: исправь файл или возьми projects/_template/state.yaml.")


def read_checked(slug) -> tuple[dict | None, str]:
    """state.yaml для CLI и статуса: битый файл — не traceback, а (None, сообщение)."""
    try:
        st = load(slug)
        if not isinstance(st, dict) or not isinstance(st.get("done"), dict) or not isinstance(st.get("human"), list):
            raise ValueError("структура")
        return st, ""
    except Exception:  # noqa: BLE001 — любой разбор YAML или структуры сводится к одному сообщению
        return None, BROKEN_MSG


def _fail(msg: str) -> int:
    print(f"Ошибка: {msg}", file=sys.stderr)
    return 3


def _norm(x) -> str:
    return " ".join(str(x or "").split()).casefold()


def _waiting_point(w) -> str:
    if isinstance(w, dict):
        return str(w.get("point") or "")
    return str(w) if w else ""


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(
        description="Состояние проекта: переход шага, ожидание ответа человека, его снятие, печать state.yaml.",
        epilog="Коды выхода: 0 — готово, 3 — ошибка использования (с подсказкой, что сделать).")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("step", help="перейти на шаг: <n 1–6> <имя>")
    s1.add_argument("n", type=int, help="номер шага 1–6")
    s1.add_argument("name", help="frame | collect | research | options | strategy | after-decision")
    s2 = sub.add_parser("wait", help='встать в ожидание человека: "<точка N>" "<вопрос>"')
    s2.add_argument("point", help='например "точка 1"')
    s2.add_argument("question", help="вопрос человеку (с пометкой «от ответа зависит: …»)")
    s3 = sub.add_parser("resolve", help='снять ожидание после ответа: "<точка N>" --summary "…" --minutes N')
    s3.add_argument("point")
    s3.add_argument("--summary", required=True, help="что решил человек")
    s3.add_argument("--minutes", type=float, required=True, help="минуты человека на эту точку (пишутся в журнал один раз)")
    sub.add_parser("show", help="напечатать state.yaml")
    a = ap.parse_args(argv)
    try:
        project_path(a.project)
    except SystemExit:
        return 3  # сообщение «проекта нет, что сделать» уже напечатано
    slug = a.project
    _, err = read_checked(slug)
    if err:
        return _fail(err)
    if a.cmd == "step":
        want = STEP_NAMES.get(a.n)
        if want is None or a.name != want:
            ok = ", ".join(f"{n} {nm}" for n, nm in STEP_NAMES.items())
            return _fail(f"шаг «{a.n} {a.name}» не существует. Что сделать: возьми одну из пар: {ok}.")
        set_step(slug, a.n, a.name)
        print(f"Шаг: {a.n} {a.name}.")
    elif a.cmd == "wait":
        if not a.point.strip() or not a.question.strip():
            return _fail('нужны точка и вопрос. Что сделать: `state.py wait "точка 1" "<вопрос>"`.')
        w = load(slug).get("waiting")
        if w:
            wp = _waiting_point(w)
            how = "`python tools/check.py --resolve \"<решение>\" --minutes N`" if _norm(wp) == "check" else                   f'`python tools/state.py resolve "{wp}" --summary "…" --minutes N`'
            return _fail(f"уже ждём «{wp}». Что сделать: сначала закрой текущую точку: {how}.")
        wait_human(slug, a.point.strip(), a.question.strip())
        print(f"Жду человека: {a.point.strip()}.")
    elif a.cmd == "resolve":
        if _norm(a.point) == "check":
            return _fail('ожидание «check» снимает только `python tools/check.py --resolve "<решение>" --minutes N` '
                         "(он же сбрасывает счётчик check_fails). Что сделать: вызови эту команду.")
        if not math.isfinite(a.minutes) or a.minutes < 0:
            return _fail("минуты должны быть числом ≥ 0. Что сделать: укажи --minutes N.")
        w = load(slug).get("waiting")
        if not w:
            return _fail(f"ничего не ждёт ответа (повторный resolve удвоил бы минуты). Что сделать: сначала `state.py wait \"{a.point}\" \"<вопрос>\"`, "
                         "а время вне точек пиши `log.py human`.")
        if _norm(_waiting_point(w)) != _norm(a.point):
            return _fail(f"ждём «{_waiting_point(w)}», а не «{a.point}». Что сделать: укажи ту же точку, что в `wait`.")
        resolve_human(slug, a.point.strip(), a.summary.strip(), a.minutes)
        print(f"Снято ожидание: {a.point.strip()}, {a.minutes:g} мин записано в журнал.")
    else:
        import yaml
        print(yaml.safe_dump(load(slug), allow_unicode=True, sort_keys=False).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
