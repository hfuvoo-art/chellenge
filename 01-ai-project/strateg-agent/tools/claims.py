# Реестр утверждений (claims.jsonl): типы, статусы, поиск; без него факты не отличить от выводов агента, а правки и повторные запуски плодят дубликаты.
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from rapidfuzz import fuzz, utils  # noqa: E402

from tools.common import (  # noqa: E402
    append_jsonl, die, next_id, project_path, read_jsonl, setup_stdio, write_text_atomic,
)
from tools.log import event  # noqa: E402

TYPES = {"fact", "estimate", "hypothesis", "forecast", "synthetic", "interview", "conclusion", "observation"}
STATUSES = ("active", "disputed", "superseded", "retracted")
AGENT_TYPES = {"conclusion", "hypothesis", "forecast"}  # то, что может писать агент (У10)
FACT_WRITERS = ("extract.py", "analyze.py", "user")  # кто вправе писать fact (У10)
CELL_RE = re.compile(r"^.+!\$?[A-Za-z]{1,3}\$?\d+$")  # Лист!C14
SEARCH_THRESHOLD = 60


def _path(slug: str | None) -> Path:
    return project_path(slug) / "claims.jsonl"


def _writer(c: dict) -> str:
    return str(c.get("extracted_by") or "").strip()


def validate(c: dict) -> list[str]:
    errs: list[str] = []
    t = c.get("type")
    if not isinstance(t, str) or t not in TYPES:
        errs.append(f"type: должен быть один из {sorted(TYPES)}")
    if not str(c.get("text") or "").strip():
        errs.append("text: пустая формулировка")
    q = c.get("question", [])
    if not isinstance(q, list) or not all(isinstance(x, str) for x in q):
        errs.append('question: нужен список вида ["Q1"]')
    who = _writer(c)
    is_agent = who.lower().startswith("agent")
    if t == "fact":
        for f in ("source", "locator", "quote"):
            if not str(c.get(f) or "").strip():
                errs.append(f"{f}: fact без {f} не бывает")
        if not any(who == w or who.startswith(w + ":") for w in FACT_WRITERS):
            errs.append("extracted_by: fact пишут только extract.py, analyze.py и user; ответ агента — conclusion, hypothesis или forecast")
    elif is_agent and isinstance(t, str) and t in TYPES and t not in AGENT_TYPES:
        errs.append(f"type: агент пишет только {sorted(AGENT_TYPES)}, а не {t}")
    has_cell = bool(CELL_RE.match(str(c.get("locator") or "")))
    for f in ("dims", "value"):
        if c.get(f) is not None and not has_cell:
            errs.append(f"{f}: только для табличного факта с локатором вида Лист!C14")
    if c.get("dims") is not None and not (isinstance(c["dims"], dict) and all(isinstance(k, str) for k in c["dims"])):
        errs.append("dims: нужен объект {измерение: значение}")
    v = c.get("value")
    if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)):
        errs.append("value: нужно конечное число")
    return errs


def load(slug: str | None) -> list[dict]:
    return read_jsonl(_path(slug))


def get(slug: str | None, cid: str) -> dict:
    for c in load(slug):
        if c["id"] == cid:
            return c
    raise KeyError(f"утверждения {cid} нет. Что сделать: `python tools/claims.py list`.")


def active(slug: str | None) -> list[dict]:
    return [c for c in load(slug) if c.get("status") in ("active", "disputed")]


def _same(a: dict, b: dict) -> bool:
    keys = ("text", "type", "source", "locator", "quote")
    return all((a.get(k) or None) == (b.get(k) or None) for k in keys)


def add(slug: str | None, c: dict) -> str:
    errs = validate(c)
    if errs:
        raise ValueError("утверждение отклонено: " + "; ".join(errs))
    existing = load(slug)
    for e in existing:  # повторный запуск шага не плодит дубликаты; отозванное не воскресает
        if _same(e, c):
            merged = list(e.get("question") or [])
            merged += [q for q in (c.get("question") or []) if q not in merged]
            if merged != (e.get("question") or []):
                e["question"] = merged
                _save(slug, existing)
                event(slug, "claim_questions", id=e["id"], question=merged)
            return e["id"]
    rec = {k: v for k, v in c.items() if k not in ("id", "status", "supersedes", "status_reason", "status_by")}
    rec["id"] = next_id("C", [e["id"] for e in existing])
    rec["status"] = "active"
    rec.setdefault("question", [])
    rec["supersedes"] = None
    append_jsonl(_path(slug), rec)
    event(slug, "claim_add", id=rec["id"], type=rec["type"], extracted_by=_writer(rec))
    return rec["id"]


def _save(slug: str | None, items: list[dict]) -> None:
    write_text_atomic(_path(slug), "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in items))


def set_status(slug: str | None, cid: str, status: str, *, by: str | None = None, reason: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"статус должен быть один из {list(STATUSES)}")
    if not (reason or "").strip():
        raise ValueError(f"для смены статуса на {status} нужна причина (--reason)")
    if status == "superseded" and not by:
        raise ValueError("для superseded нужно указать, чем заменено (--by C-nnn)")
    items = load(slug)
    byid = {c["id"]: c for c in items}
    if cid not in byid:
        raise KeyError(f"утверждения {cid} нет. Что сделать: `python tools/claims.py list`.")
    if status == "superseded":
        if byid[cid]["status"] == "superseded":
            raise ValueError(f"{cid} уже заменено ({byid[cid].get('status_by')}). Что сделать: менять статус нового утверждения, а не повторять supersede.")
        if by not in byid or by == cid:
            raise ValueError(f"заменяющего утверждения {by} нет или оно совпадает с {cid}")
        if byid[by]["status"] in ("retracted", "superseded"):
            raise ValueError(f"{by} имеет статус {byid[by]['status']} и не может заменять. Что сделать: указать действующее утверждение.")
    c = byid[cid]
    c["status"], c["status_reason"], c["status_by"] = status, reason, by
    if status == "superseded":
        byid[by]["supersedes"] = cid
    _save(slug, items)
    event(slug, "claim_status", id=cid, status=status, by=by, reason=reason)


def search(slug: str | None, text: str, types=None, limit: int = 20) -> list[dict]:
    scored = []
    for c in active(slug):
        if types and c.get("type") not in types:
            continue
        s = max(fuzz.token_set_ratio(text, c.get(f) or "", processor=utils.default_process) for f in ("text", "quote"))
        if s >= SEARCH_THRESHOLD:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])  # sort устойчивый: при равенстве порядок записи
    return [c for _, c in scored[:limit]]


def _line(c: dict) -> str:
    where = f" [{c['source']} {c['locator']}]" if c.get("source") else ""
    return f"{c['id']} {c['type']}/{c['status']}{where} {c['text']}"


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(description="Реестр утверждений проекта (claims.jsonl).")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add", help="добавить утверждение из JSON")
    s.add_argument("--json", required=True, help='запись: {"text":…,"type":…,"source":…,"locator":…,"quote":…}')
    s = sub.add_parser("list", help="показать утверждения")
    s.add_argument("--type", choices=sorted(TYPES))
    s.add_argument("--question", help="например Q1")
    s.add_argument("--status", choices=STATUSES)
    sub.add_parser("show", help="показать одно утверждение целиком").add_argument("id")
    s = sub.add_parser("search", help="найти по формулировке или цитате")
    s.add_argument("text")
    s.add_argument("--type", choices=sorted(TYPES), action="append")
    s.add_argument("--limit", type=int, default=20)
    for name, hlp in (("retract", "отозвать (нужна причина)"), ("dispute", "пометить спорным (нужна причина)")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("id")
        s.add_argument("--reason", required=True)
    s = sub.add_parser("supersede", help="заменить утверждение новым")
    s.add_argument("id")
    s.add_argument("--by", required=True, help="id нового утверждения")
    s.add_argument("--reason", default="заменено новым утверждением")
    a = ap.parse_args(argv)
    slug = a.project
    try:
        if a.cmd == "add":
            try:
                c = json.loads(a.json)
            except json.JSONDecodeError as e:
                die(f"--json не разобран ({e}). Что сделать: передать корректный JSON-объект в кавычках.")
            if not isinstance(c, dict):
                die("--json должен быть объектом {…}.")
            print(add(slug, c))
        elif a.cmd == "list":
            for c in load(slug):
                if (a.type and c["type"] != a.type) or (a.status and c["status"] != a.status) \
                        or (a.question and a.question not in c.get("question", [])):
                    continue
                print(_line(c))
        elif a.cmd == "show":
            c = get(slug, a.id)
            print(json.dumps(c, ensure_ascii=False, indent=2))
            if c.get("status_reason"):
                print(f"причина: {c['status_reason']}")
        elif a.cmd == "search":
            for c in search(slug, a.text, a.type, a.limit):
                print(_line(c))
        elif a.cmd == "supersede":
            set_status(slug, a.id, "superseded", by=a.by, reason=a.reason)
            print(f"{a.id} заменено на {a.by}.")
        else:
            set_status(slug, a.id, "retracted" if a.cmd == "retract" else "disputed", reason=a.reason)
            print(f"{a.id}: статус обновлён.")
    except (ValueError, KeyError) as e:
        die(str(e.args[0]) if isinstance(e, KeyError) else str(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
