# Пересмотр при новых данных: что затронуто новым источником или изменённым утверждением (утверждения, варианты, разделы стратегии, решения, обещания); без него новая версия страницы проходит мимо стратегии.
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from tools import check, claims, review as review_mod  # noqa: E402
from tools.common import project_path, read_text, setup_stdio, write_text_atomic  # noqa: E402
from tools.log import event  # noqa: E402

REF_RE = re.compile(r"\bC-\d+\b")
SRC_RE = re.compile(r"\bS-\d+\b")
BLOCK_PREFIX = "## Пересмотр от "
LIVE = ("active", "disputed")


@dataclass
class ImpactReport:
    claims: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    promises: list[str] = field(default_factory=list)  # F-n обещаний, чья функция опирается на затронутое
    sources: list[str] = field(default_factory=list)   # источники, чьи абзацы пересматриваются (сам и прошлые версии)

    def empty(self) -> bool:
        return not (self.claims or self.options or self.sections or self.decisions or self.promises)


def _strategy_sections(slug) -> list[dict]:
    text = check._doc(slug, "strategy.md")
    secs = check._sections(text) if text else []
    return [s for s in secs if not s["title"].startswith("Пересмотр от")]


def graph(slug) -> dict:
    """Рёбра проекта: claim_source {C: S}, source_supersedes {новый S: старый S}, claim_supersedes {новый C: старый C},
    options {O: [C]}, sections {заголовок: [C]}, features {F: [C]} (basis), promises {F: [текст обещания]},
    decisions {D: {basis: [C], depends_on: [F]}}."""
    cl = claims.load(slug)
    g: dict = {
        "claim_source": {c["id"]: c["source"] for c in cl if c.get("source")},
        "source_supersedes": {new: old for old, new in review_mod.superseded_sources(slug).items()},
        "claim_supersedes": {c["id"]: c["supersedes"] for c in cl if c.get("supersedes")},
        "options": {}, "sections": {}, "features": {}, "promises": {}, "decisions": {},
    }
    opt = check._doc(slug, "options.md")
    for b in check._options_blocks(opt) if opt else []:
        g["options"][b["id"]] = sorted(set(REF_RE.findall("\n".join(b["lines"]))))
    for s in _strategy_sections(slug):
        refs = sorted(set(REF_RE.findall("\n".join(s["lines"]))))
        if refs:
            g["sections"][s["title"]] = refs
    feats, _ = check._features(slug)
    for fid, f in feats.items():
        g["features"][fid] = [str(x) for x in (f.get("basis") or [])]
    for s in _strategy_sections(slug):
        if s["norm"] == check._norm_title(check.PROMISES):
            for ln in s["lines"]:
                m = check.PROMISE_RE.match(ln)
                if m:
                    g["promises"].setdefault(m.group(2), []).append(m.group(1))
    for d in review_mod.load_decisions(slug):
        g["decisions"][str(d["id"])] = {"basis": [str(x) for x in (d.get("basis") or [])],
                                        "depends_on": [str(x) for x in (d.get("depends_on") or [])]}
    return g


def _source_chain(g: dict, sid: str) -> list[str]:
    chain, cur = [sid], sid
    while cur in g["source_supersedes"] and g["source_supersedes"][cur] not in chain:
        cur = g["source_supersedes"][cur]
        chain.append(cur)
    return chain


def _claim_closure(g: dict, start: set[str]) -> set[str]:
    """Цепочки supersedes в обе стороны: заменённое и заменяющее утверждение пересматриваются вместе."""
    edges: dict[str, set[str]] = {}
    for new, old in g["claim_supersedes"].items():
        edges.setdefault(new, set()).add(old)
        edges.setdefault(old, set()).add(new)
    seen, todo = set(start), list(start)
    while todo:
        for nb in edges.get(todo.pop(), ()):
            if nb not in seen:
                seen.add(nb)
                todo.append(nb)
    return seen


def _num_key(x: str):
    m = re.search(r"\d+", x)
    return (x[0], int(m.group()) if m else 0, x)


def impact(slug, *, source: str | None = None, claim: str | None = None) -> ImpactReport:
    """Затронутое новым источником (его утверждения и утверждения заменённых им версий) или утверждением (с цепочкой supersedes)."""
    if bool(source) == bool(claim):
        raise ValueError("укажи ровно одно: источник S-nnn или --claim C-nnn")
    g = graph(slug)
    known = {c["id"] for c in claims.load(slug)}
    sources: list[str] = []
    if source:
        sources = _source_chain(g, source)
        start = {c for c, s in g["claim_source"].items() if s in sources}
        if not start and source not in g["source_supersedes"] and source not in g["source_supersedes"].values() \
                and not (project_path(slug) / "sources.yaml").is_file():
            raise ValueError(f"источник {source} не найден. Что сделать: `python tools/ingest.py` или проверь sources.yaml.")
    else:
        if claim not in known:
            raise ValueError(f"утверждения {claim} нет. Что сделать: `python tools/claims.py list`.")
        start = {claim}
    aff = _claim_closure(g, start)
    r = ImpactReport(claims=sorted(aff, key=_num_key), sources=sources)
    r.options = sorted((o for o, refs in g["options"].items() if aff & set(refs)), key=_num_key)
    src_set = set(sources)
    for s in _strategy_sections(slug):
        body = "\n".join(s["lines"])
        if aff & set(REF_RE.findall(body)) or (src_set and src_set & set(SRC_RE.findall(body))):
            r.sections.append(s["title"])
    feats = {f for f, basis in g["features"].items() if aff & set(basis)}
    r.promises = sorted((f for f in feats if f in g["promises"]), key=_num_key)
    r.decisions = sorted((d for d, v in g["decisions"].items() if aff & set(v["basis"]) or feats & set(v["depends_on"])),
                         key=_num_key)
    return r


def render_block(slug, r: ImpactReport, today: date, reason: str) -> str:
    """Текст блока для strategy.md. Заменённые и отозванные утверждения даны номером без «C-», чтобы check.py (проверка 4) не принял их за ссылки."""
    status = {c["id"]: c.get("status") for c in claims.load(slug)}
    live = [f"[{c}]" for c in r.claims if status.get(c) in LIVE]
    dead = [f"№{c[2:]} ({status.get(c)})" for c in r.claims if status.get(c) not in LIVE]
    def line(label, items):
        return f"- {label}: {', '.join(items) if items else 'нет'}"
    return "\n".join([
        f"{BLOCK_PREFIX}{today.isoformat()}", "",
        f"Повод: {reason}.", "",
        "Затронуто (пересчитывать только это):",
        line("действующие утверждения", live),
        line("заменённые или отозванные утверждения", dead),
        line("варианты", r.options),
        line("разделы стратегии", [f"«{t}»" for t in r.sections]),
        line("решения", r.decisions),
        line("обещания (функции продукта)", r.promises),
        "", "Что изменилось и что осталось: заполняет агент после пересчёта (`claims.py supersede|retract|dispute`, затем `check.py --only 1,2,3,4`).", "",
    ])


def write_block(slug, r: ImpactReport, *, today: date | None = None, reason: str = "") -> bool:
    """Дописывает в конец strategy.md блок «Пересмотр от <дата>». Не больше одного на дату: повтор ничего не меняет и возвращает False."""
    today = today or date.today()
    p = project_path(slug) / "strategy.md"
    if not p.is_file():
        raise ValueError("strategy.md нет. Что сделать: пересмотр пишется в готовую стратегию (шаг 5).")
    text = read_text(p)
    head = f"{BLOCK_PREFIX}{today.isoformat()}"
    if any(ln.strip() == head for ln in text.splitlines()):
        return False
    write_text_atomic(p, text.rstrip("\n") + "\n\n" + render_block(slug, r, today, reason or "новые данные"))
    event(slug, "impact_block", date=today.isoformat(), claims=r.claims, options=r.options, decisions=r.decisions)
    return True


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(
        description="Пересмотр при новых данных: что затронуто источником S-nnn или утверждением C-nnn (утверждения, варианты, разделы стратегии, решения, обещания).")
    ap.add_argument("source", nargs="?", help="источник S-nnn (его утверждения и утверждения заменённых им версий)")
    ap.add_argument("--claim", help="утверждение C-nnn (с цепочкой supersedes)")
    ap.add_argument("--write", action="store_true", help="дописать в strategy.md блок «Пересмотр от <дата>» (не больше одного на дату)")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    a = ap.parse_args(argv)
    try:
        r = impact(a.project, source=a.source, claim=a.claim)
    except (ValueError, KeyError) as e:
        print(e.args[0] if e.args else e)
        return 3
    print(f"Затронуто. Утверждения: {', '.join(r.claims) or 'нет'}")
    print(f"Варианты: {', '.join(r.options) or 'нет'}")
    print(f"Разделы стратегии: {', '.join(r.sections) or 'нет'}")
    print(f"Решения: {', '.join(r.decisions) or 'нет'}")
    print(f"Обещания: {', '.join(r.promises) or 'нет'}")
    if a.write:
        try:
            wrote = write_block(a.project, r, reason=f"источник {a.source}" if a.source else f"утверждение {a.claim}")
        except ValueError as e:
            print(e)
            return 3
        print("Блок записан в strategy.md." if wrote else "Блок за сегодня уже есть в strategy.md: не дублирую.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
