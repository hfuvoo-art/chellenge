# Извлечение утверждений из источника по частям (≤12 000 симв.) с возобновлением, эскалацией lite→pro→модель среды/человек и режимом без ключа; без него реестр утверждений наполнять нечем, а обрыв или плохой ответ модели дублируют или молча теряют части.
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import check, claims, ingest, llm, state  # noqa: E402
from tools.common import ROOT, project_path, read_jsonl, read_text, setup_stdio  # noqa: E402
from tools.log import event  # noqa: E402
from tools.numparse import normalize_quote  # noqa: E402

PART_LIMIT = 12_000
PROMPT_PATH = ROOT / "prompts" / "extract.md"
DROP_ESCALATE_SHARE = 0.5  # отброшено больше этой доли утверждений части: часть уходит на pro
MIN_QUOTE = 25  # символов после нормализации: короче — не цитата
EST_PROMPT_TOKENS = 1500  # системный промпт + вопросы
EST_OUT_TOKENS = 1000
CHARS_PER_TOKEN = 3  # 12 000 символов ≈ 4 000 токенов
ESTIMATE_PREFIX = "По оценке источника: "
ROUTES = ("claude-code", "opencode", "cursor", "other")
ENV_WHO = "extract.py:env-model"
MARKER_RE = ingest.MARKER_RE
CELL_LOC_RE = ingest.CELL_LOC_RE
CELL_QUOTE_RE = re.compile(r"^\S+!\$?[A-Za-z]{1,3}\$?\d+\s")  # строка таблицы «Лист!C14 …»
HEADER_RE = re.compile(r"^<!--\s*S-\d+\s*\|.*-->$")
QLINE_RE = re.compile(r"^\s*(?:[-*]\s*)?(Q\d+)\s*[:.)]?\s*(.+?)\s*$", re.M)
SID_RE = re.compile(r"^S-\d+$")


@dataclass
class Part:
    idx: int  # с 1
    text: str
    first_marker: str | None
    last_marker: str | None


@dataclass
class ExtractReport:
    parts_total: int = 0
    parts_cached: int = 0
    claims_added: int = 0
    dropped_table_facts: int = 0
    escalations: int = 0
    rub: float | None = 0.0  # None: цена хотя бы одного вызова неизвестна (У12)
    pending: list[int] = field(default_factory=list)  # части без результата (ждут человека или модель среды)
    dropped_quotes: int = 0  # отброшено поштучно (цитата не прошла проверку 1)
    emitted: list[Path] = field(default_factory=list)  # пути для ответа модели среды
    action_ids: dict[int, str] = field(default_factory=dict)


# ---------- части ----------

def _units(md: str) -> list[tuple[str, str | None, str | None]]:
    """Абзацы с маркерами: (текст, маркер в начале, маркер в конце). Служебная шапка источника отбрасывается."""
    units: list[tuple[str, str | None, str | None]] = []
    cur: str | None = None
    pre = ""
    pre_start: str | None = None
    for chunk in re.split(r"\n\s*\n", md.replace("\r\n", "\n")):
        c = chunk.strip()
        if not c or HEADER_RE.match(c):
            continue
        start = cur
        seen_body = False
        has_body = False
        for ln in c.splitlines():
            m = MARKER_RE.match(ln.strip())
            if m:
                cur = m.group(1)
                if not seen_body:
                    start = cur
            elif ln.strip():
                seen_body = has_body = True
        if not has_body:  # только маркер: приклеиваем к следующему абзацу
            if not pre:
                pre_start = start
            pre = (pre + "\n" if pre else "") + c
            continue
        if pre:
            units.append((pre + "\n" + c, pre_start, cur))
            pre = ""
        else:
            units.append((c, start, cur))
    return units


def split_parts(md: str, limit: int = PART_LIMIT) -> list[Part]:
    """Части ≤limit символов по абзацам; следующая часть начинается с последнего абзаца предыдущей (перекрытие 1 абзац).
    Ограничения: если последний абзац и следующий вместе не влезают в limit, перекрытия нет; абзац длиннее limit режется жёстко."""
    units: list[tuple[str, str | None, str | None]] = []
    for text, a, b in _units(md):
        while len(text) > limit:  # абзац длиннее части: режем жёстко
            units.append((text[:limit], a, b))
            text, a = text[limit:], b
        if text.strip():
            units.append((text, a, b))
    parts: list[Part] = []
    cur: list[tuple[str, str | None, str | None]] = []
    size = 0

    def flush():
        parts.append(Part(len(parts) + 1, "\n\n".join(u[0] for u in cur), cur[0][1], cur[-1][2]))

    for u in units:
        add = len(u[0]) + (2 if cur else 0)
        if cur and size + add > limit:
            flush()
            last = cur[-1]
            cur = [last] if len(last[0]) + 2 + len(u[0]) <= limit else []
            size = len(last[0]) if cur else 0
            add = len(u[0]) + (2 if cur else 0)
        cur.append(u)
        size += add
    if cur:
        flush()
    return parts


# ---------- вход ----------

def load_prompt_file(path) -> str:
    """Текст промпта без служебного комментария первой строки (общая функция extract/critic/respond)."""
    t = read_text(path)
    return re.sub(r"\A\s*<!--.*?-->\s*", "", t, flags=re.S).strip()


def load_prompt() -> str:
    return load_prompt_file(PROMPT_PATH)


def _questions(slug: str, wanted: list[str] | None) -> list[tuple[str, str]]:
    qfile = project_path(slug) / "questions.md"
    allq = QLINE_RE.findall(read_text(qfile)) if qfile.is_file() else []
    if wanted is None:
        return allq
    byc = dict(allq)
    missing = [q for q in wanted if q not in byc]
    if missing:
        raise ValueError(f"вопроса {missing[0]} нет в questions.md. Что сделать: добавьте строку `- {missing[0]}: …` в questions.md и повторите.")
    return [(q, byc[q]) for q in wanted]


def _route() -> str:
    r = llm._env("AGENT_ROUTE").lower()
    if r in ROUTES:
        return r
    return "claude-code" if os.environ.get("CLAUDECODE") == "1" else "other"


def _source(slug: str, sid: str) -> tuple[str, dict]:
    p = project_path(slug) / "materials" / f"{sid}.md"
    ent = next((s for s in ingest._load_sources(slug) if s.get("id") == sid), None)
    if not p.is_file() or ent is None:
        raise ValueError(f"источника {sid} нет в проекте. Что сделать: сначала `python tools/ingest.py <файл или адрес> --found-by user`, список в sources.yaml.")
    return read_text(p), ent


def _label(text: str, suspicious) -> str:
    """Подозрительные абзацы помечаются в промпте; в цитату метка не попадает (цитата сверяется с исходным текстом)."""
    # разделители промпта внутри текста источника обезвреживаются (цитата сверяется с исходником, не с промптом)
    text = text.replace("ИСТОЧНИК>>>", "ИСТОЧНИК> >>").replace("<<<ИСТОЧНИК", "< <<ИСТОЧНИК")
    sus = {str(x) for x in (suspicious or [])}
    if not sus:
        return text
    out = []
    for ln in text.split("\n"):
        m = MARKER_RE.match(ln.strip())
        out.append(ln.rstrip() + " [suspicious]" if m and m.group(1) in sus else ln)
    return "\n".join(out)


def _user_prompt(sid: str, part: Part, total: int, qs, suspicious) -> str:
    qtext = "\n".join(f"{q}: {t}" for q, t in qs)
    return (f"Вопросы исследования:\n{qtext}\n\n" if qtext else "") + \
        f"Фрагмент {part.idx} из {total} (источник: {sid}).\n\n<<<ИСТОЧНИК\n{_label(part.text, suspicious)}\nИСТОЧНИК>>>"


def _aid(sid: str, part: Part, qs) -> str:
    qtext = "\n".join(f"{q}: {t}" for q, t in qs)
    return state.action_id("extract", f"{sid}:part-{part.idx:02d}", part.text + "\n" + qtext)


def _model_label(role: str) -> str:
    m = llm._model_for(role)
    if m.startswith("gpt://"):
        m = m[len("gpt://"):].split("/", 1)[-1]
    return m or "модель не задана"


# ---------- проверка и запись ----------

def _segments(part: Part) -> list[tuple[str | None, str]]:
    """Часть, разрезанная по маркерам: (маркер, текст без маркерной строки)."""
    segs: list[tuple[str | None, list[str]]] = [(part.first_marker, [])]
    for ln in part.text.split("\n"):
        m = MARKER_RE.match(ln.strip())
        if m:
            segs.append((m.group(1), []))
        else:
            segs[-1][1].append(ln)
    return [(mk, "\n".join(ls).strip()) for mk, ls in segs if "".join(ls).strip()]


def _find_locator(quote: str, part: Part, model_loc: str) -> tuple[str | None, str]:
    """Локатор определяет код: маркер того абзаца, где цитата найдена дословно (проверка 1). (локатор | None, причина отказа).
    Короче MIN_QUOTE принимается, только если после нормализации равна целому абзацу («Цена: 650 ₽ в месяц»)."""
    nq = normalize_quote(quote)
    segs = _segments(part)
    if len(nq) < MIN_QUOTE:
        for marker, body in segs:
            if nq and normalize_quote(body) == nq:
                return (marker or model_loc or None), ""
        return None, f"цитата короче {MIN_QUOTE} символов и не равна целому абзацу"
    reason = "цитаты нет в тексте части"
    for marker, body in segs:
        f = check.check_quote({"id": "?", "quote": quote}, body)
        if f.level == "OK":
            return (marker or model_loc or None), ""
        if "цитаты нет в указанном разделе" not in f.msg:
            reason = f.msg
    return None, reason


def _screen(items, part: Part, codes: list[str], who: str) -> tuple[list[dict], int, list[str]]:
    """(принятые, отброшено табличных, причины отбора). Поштучно: дословная цитата в одном абзаце проходит, остальные отбрасываются.
    Табличных fact LLM не создаёт."""
    ok: list[dict] = []
    tables = 0
    rejected: list[str] = []
    for c in items:
        if not isinstance(c, dict):
            rejected.append("элемент ответа не объект")
            continue
        quote = str(c.get("quote") or "").strip()
        model_loc = str(c.get("locator") or "").strip()
        if CELL_LOC_RE.match(model_loc) or CELL_QUOTE_RE.match(quote):
            tables += 1
            continue
        text = str(c.get("text") or "").strip()
        t = c.get("type")
        if t == "estimate":  # оценка из текста источника — fact с цитатой; estimate только расчёт с calc/
            t = "fact"
            if not text.startswith(ESTIMATE_PREFIX):
                text = ESTIMATE_PREFIX + text
        elif t != "forecast":
            t = "fact"
        loc, why = _find_locator(quote, part, model_loc)
        if loc is None:
            rejected.append(f"«{quote[:60]}»: {why}")
            continue
        if not text:
            rejected.append(f"«{quote[:60]}»: пустой text")
            continue
        q = [x for x in (c.get("question") or []) if isinstance(x, str) and (x in codes if codes else re.fullmatch(r"Q\d+", x))]
        ok.append({"type": t, "text": text, "locator": loc, "quote": quote, "question": q or codes[:1] or ["Q1"], "extracted_by": who})
    return ok, tables, rejected


def _dedup(items: list[dict]) -> list[dict]:
    """Одна цитата — одно утверждение (первое); вопросы объединяются."""
    out: dict[str, dict] = {}
    for it in items:
        k = normalize_quote(it["quote"])
        if k in out:
            out[k]["question"] = list(dict.fromkeys(out[k]["question"] + it["question"]))
        else:
            out[k] = {**it, "question": list(it["question"])}
    return list(out.values())


def _commit(slug: str, sid: str, items: list[dict]) -> int:
    """Записывает принятое в claims.jsonl; то же место и та же цитата не плодят записей (вопросы объединяются)."""
    existing = claims.load(slug)
    by_quote = {(e.get("source"), normalize_quote(e.get("quote") or "")): e for e in existing}
    known = {e["id"] for e in existing}
    added = 0
    for it in _dedup(items):
        e = by_quote.get((sid, normalize_quote(it["quote"])))
        if e is not None:
            merged = [q for q in dict.fromkeys(list(e.get("question") or []) + it["question"])]
            cid = claims.add(slug, {**e, "question": merged})
        else:
            cid = claims.add(slug, {**it, "source": sid})
        if cid not in known:
            known.add(cid)
            added += 1
    return added


@dataclass
class Tier:
    valid: bool = False  # получен разобранный ответ со списком claims
    accepted: list[dict] = field(default_factory=list)
    tables: int = 0
    rejected: list[str] = field(default_factory=list)
    weak: bool = False  # ответ валиден, но принято 0 при непустом или отброшено больше DROP_ESCALATE_SHARE
    why: str = ""


def _try(slug, role, system, user, aid, category, part, codes) -> Tier:
    """Один ярус: вызов модели и поштучный отбор утверждений; в журнал — claims_dropped."""
    try:
        obj, r = llm.chat_json([{"role": "system", "content": system}, {"role": "user", "content": user}],
                               role=role, slug=slug, action_id=aid, required_keys=["claims"],
                               category=category, max_tokens=4000, temperature=0)
    except llm.LLMJSONError:
        return Tier(why="ответ не JSON даже после ремонта")
    except llm.LLMUnavailable as e:
        return Tier(why=f"модель недоступна: {e}")
    except llm.NoKeyError as e:
        return Tier(why=f"роль «{role}» не настроена: {e}")
    if not isinstance(obj.get("claims"), list):
        return Tier(why="«claims» не список")
    ok, tables, rej = _screen(obj["claims"], part, codes, f"extract.py:{_model_label(role)}")
    t = Tier(valid=True, accepted=ok, tables=tables, rejected=rej)
    seen = len(ok) + len(rej)
    if seen and (not ok or len(rej) > DROP_ESCALATE_SHARE * seen):
        t.weak = True
        t.why = f"принято {len(ok)} из {seen}: цитаты не прошли проверку 1"
    if rej:
        event(slug, "claims_dropped", action_id=aid, role=role, count=len(rej), reasons=rej[:5])
    return t


def _rub_for(slug, aids) -> float | None:
    """₽ по событиям llm этих action_id (включая неудачные ярусы, ремонты и эскалации); None, если цена хоть одного неизвестна."""
    want = set(aids)
    total = 0.0
    for e in read_jsonl(project_path(slug) / "log.jsonl"):
        if e.get("kind") == "llm" and e.get("action_id") in want:
            if e.get("rub") is None:
                return None
            total += e["rub"]
    return round(total, 6)


# ---------- режим без ключа ----------

def _prompt_paths(slug: str, aid: str) -> tuple[Path, Path]:
    base = project_path(slug) / "cache" / "prompts"
    stem = aid.replace(":", "_")  # «:» нельзя в имени файла на Windows
    return base / f"{stem}.json", base / f"{stem}.prompt.txt"


def _qflags(questions) -> str:
    return "".join(f" --question {q}" for q in (questions or []))


def write_prompt(slug, aid, system, user, *, title, label, apply_cmd, show_prompt, shape="один JSON-объект") -> Path:
    """Общая механика режима без ключа (У3): промпт в cache/prompts/<action_id>.prompt.txt, подсказка, куда класть ответ.
    Возвращает путь файла ответа модели среды; в apply_cmd «{ans}» заменяется этим путём."""
    from tools.common import write_text_atomic
    ans, prm = _prompt_paths(slug, aid)
    write_text_atomic(prm, f"{system}\n\n---\n\n{user}\n")
    if show_prompt:
        print(f"=== ПРОМПТ ({title}) ===\n{system}\n\n---\n\n{user}\n=== КОНЕЦ ПРОМПТА ===")
    print(f"Промпт {label}: {prm}\n"
          f"Что сделать: модель среды читает промпт, кладёт ответ ({shape}) в {ans}, затем: {apply_cmd.replace('{ans}', str(ans))}")
    return ans


def _emit(slug, sid, part, system, user, aid, *, show_prompt: bool, questions=None) -> Path:
    return write_prompt(slug, aid, system, user, title=f"источник {sid}, часть {part.idx}", label=f"части {part.idx}",
                        apply_cmd=f"python tools/extract.py {sid}{_qflags(questions)} --apply \"{{ans}}\" --part {part.idx} -p {slug}",
                        show_prompt=show_prompt)


def apply_result(slug: str, sid: str, part_idx: int, path, questions: list[str] | None = None) -> int:
    """Применяет ответ модели среды к части: те же проверки, что у ответа Yandex, поштучно. Возвращает число новых утверждений.
    Прошедшие принимаются, отклонённые перечисляются; принято 0 при непустом ответе — отказ, часть не done."""
    md, ent = _source(slug, sid)
    parts = split_parts(md, PART_LIMIT)
    if not 1 <= part_idx <= len(parts):
        raise ValueError(f"в {sid} частей {len(parts)}, а запрошена {part_idx}. Что сделать: укажите --part от 1 до {len(parts)}.")
    part = parts[part_idx - 1]
    qs = _questions(slug, questions)
    codes = [q for q, _ in qs]
    aid = _aid(sid, part, qs)
    if state.is_done(slug, aid):
        print(f"Часть {part_idx} уже применена: ничего не записано.")
        return 0
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"файла ответа {p} нет. Что сделать: положите JSON ответа модели в этот файл и повторите.")
    try:
        obj = llm._extract_json(read_text(p))
    except ValueError:
        obj = None
    if not isinstance(obj, dict) or not isinstance(obj.get("claims"), list):
        event(slug, "apply_rejected", action_id=aid, reason="не JSON с ключом claims")
        raise ValueError(f"ответ в {p.name} — не JSON-объект с ключом «claims». Что сделать: верните только JSON вида {{\"claims\":[…]}}, без пояснений.")
    ok, _tables, rej = _screen(obj["claims"], part, codes, ENV_WHO)
    if rej:
        event(slug, "claims_dropped", action_id=aid, role="env-model", count=len(rej), reasons=rej[:5])
    if rej and not ok:
        event(slug, "apply_rejected", action_id=aid, reason=f"ни одна цитата не прошла проверку 1 ({len(rej)})")
        raise ValueError(f"ни одно из {len(rej)} утверждений не прошло проверку цитаты. Примеры: " + "; ".join(rej[:3]) +
                         ". Что сделать: перепишите цитаты дословно из промпта (целое предложение ≥25 символов из одного абзаца) и повторите --apply; записано ничего не было.")
    if len(rej) > DROP_ESCALATE_SHARE * (len(ok) + len(rej)):  # тот же порог, что для lite → pro: слабый ответ возвращается на доработку
        event(slug, "apply_rejected", action_id=aid, reason=f"отброшено {len(rej)} из {len(ok) + len(rej)} (порог {DROP_ESCALATE_SHARE})")
        raise ValueError(f"не прошли проверку цитаты {len(rej)} из {len(ok) + len(rej)} утверждений (больше половины). Примеры: " + "; ".join(rej[:3]) +
                         ". Что сделать: перепишите эти цитаты дословно из промпта или удалите такие утверждения из ответа и повторите --apply; записано ничего не было.")
    added = _commit(slug, sid, ok)
    if rej:
        print(f"Отклонено {len(rej)} утверждений (цитата не прошла проверку 1): " + "; ".join(rej[:3]))
    state.add_degraded(slug, "env-model", f"извлечение {sid} часть {part_idx}: ответ модели среды (режим без ключа или эскалация)")
    event(slug, "env_model", action_id=aid, unit=f"{sid}:part-{part_idx:02d}",
          note="расход модели среды учитывайте вручную: python tools/log.py model <usd>")
    state.mark_done(slug, aid, {"part": part_idx, "claims": added, "degraded": "env-model"})
    event(slug, "extract_part", source=sid, part=part_idx, claims=added, via="env-model")
    return added


# ---------- основной проход ----------

def _estimate(model_role: str, parts: list[Part], qs) -> tuple[float | None, int]:
    model = llm._model_for(model_role)
    total = 0.0
    tokens = 0
    known = bool(model)
    for p in parts:
        tin = EST_PROMPT_TOKENS + len(p.text) // CHARS_PER_TOKEN
        tokens += tin + EST_OUT_TOKENS
        price = llm.price_rub(model, {"prompt_tokens": tin, "completion_tokens": EST_OUT_TOKENS}) if model else None
        if price is None:
            known = False
        else:
            total += price
    return (round(total, 4) if known else None), tokens


def extract_source(slug, sid, *, questions=None, model_role="extract", dry_run=False, emit_prompt=False) -> ExtractReport:
    md, ent = _source(slug, sid)
    qs = _questions(slug, questions)
    codes = [q for q, _ in qs]
    parts = split_parts(md, PART_LIMIT)
    rep = ExtractReport(parts_total=len(parts))
    system = load_prompt()
    suspicious = ent.get("suspicious")
    if not dry_run and not emit_prompt:
        llm._require_config(model_role, None)  # NoKeyError до любой работы: CLI подскажет --emit-prompt
    todo: list[Part] = []
    for part in parts:
        aid = _aid(sid, part, qs)
        rep.action_ids[part.idx] = aid
        if state.is_done(slug, aid):
            rep.parts_cached += 1
        else:
            todo.append(part)
    if dry_run:
        rub, tokens = _estimate(model_role, todo, qs)
        rep.rub = rub
        price = f"≈ {rub:.2f} ₽" if rub is not None else "цена неизвестна (модель или цена не заданы: config/prices.yaml, .env)"
        print(f"Оценка для {sid}: частей {len(todo)} из {len(parts)} (в кеше {rep.parts_cached}), "
              f"≈ {tokens} токенов, {price}; эскалации на pro не входят; вызовов не делаю.")
        return rep
    if emit_prompt:
        if todo:
            part = todo[0]
            rep.emitted.append(_emit(slug, sid, part, system, _user_prompt(sid, part, len(parts), qs, suspicious),
                                     rep.action_ids[part.idx], show_prompt=True, questions=questions))
            rep.pending.append(part.idx)
        else:
            print(f"Все части готовы. Дальше: python tools/check.py --only 1,2,3,4 -p {slug}")
        return rep
    failed_human: list[tuple[int, str]] = []
    for part in todo:
        aid = rep.action_ids[part.idx]
        unit = f"{sid}:part-{part.idx:02d}"
        user = _user_prompt(sid, part, len(parts), qs, suspicious)
        t1 = _try(slug, model_role, system, user, aid, "yandex", part, codes)
        tiers = [t1]
        if (not t1.valid or t1.weak) and model_role != "pro":
            rep.escalations += 1
            event(slug, "escalation", step="lite->pro", unit=unit, part=part.idx, reason=t1.why, action_id=aid)
            tiers.append(_try(slug, "pro", system, user, aid, "retry", part, codes))
        accepted = [c for t in tiers for c in t.accepted]  # принятое с lite сохраняется и объединяется с принятым от pro
        last = tiers[-1]
        saw_items = any(t.valid and (t.accepted or t.rejected) for t in tiers)
        rep.dropped_quotes += sum(len(t.rejected) for t in tiers)
        if not accepted and (not last.valid or saw_items):
            why = last.why or t1.why
            rep.escalations += 1
            rep.pending.append(part.idx)
            if _route() == "claude-code":
                event(slug, "escalation", step="pro->env-model", unit=unit, part=part.idx, reason=why, action_id=aid)
                rep.emitted.append(_emit(slug, sid, part, system, user, aid, show_prompt=False, questions=questions))
            else:
                event(slug, "escalation", step="pro->human", unit=unit, part=part.idx, reason=why, action_id=aid)
                failed_human.append((part.idx, why))
            continue
        rep.dropped_table_facts += sum(t.tables for t in tiers)
        if len(tiers) > 1 and not last.valid and t1.accepted:
            print(f"Часть {part.idx}: pro не дал ответа ({last.why}), сохранено принятое с lite: {len(t1.accepted)}.")
            event(slug, "pro_failed_kept_lite", unit=unit, part=part.idx, kept=len(t1.accepted), reason=last.why, action_id=aid)
        added = _commit(slug, sid, accepted)
        rep.claims_added += added
        state.mark_done(slug, aid, {"part": part.idx, "claims": added})
        event(slug, "extract_part", source=sid, part=part.idx, claims=added, via="yandex")
    rep.rub = _rub_for(slug, [rep.action_ids[p.idx] for p in todo])
    if failed_human:
        listing = "; ".join(f"часть {i} ({w})" for i, w in failed_human)
        state.wait_human(slug, "extract", f"Источник {sid}: не удалось извлечь {listing}. "
                         f"Что сделать: проверьте источник (скан, мусор, инъекция) и решите: повторить извлечение, "
                         f"выписать утверждения вручную (`claims.py add`) или исключить источник.")
    return rep


# ---------- CLI ----------

def _fmt_rub(rub) -> str:
    return f"{rub:.2f} ₽" if rub is not None else "цена неизвестна"


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(
        description="Извлечение утверждений из источника: режет текст на части ≤12 000 символов (перекрытие 1 абзац), "
                    "отправляет модели, поштучно проверяет цитаты и пишет утверждения в claims.jsonl. Повторный запуск не отправляет "
                    "готовые части. Без ключа: --emit-prompt и --apply.")
    ap.add_argument("source", help="номер источника, например S-003")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    ap.add_argument("--question", action="append", metavar="Q", help="только этот вопрос (например Q4); можно повторять. Без флага — все вопросы из questions.md")
    ap.add_argument("--dry-run", action="store_true", help="только оценка частей, токенов и цены; вызовов нет")
    ap.add_argument("--emit-prompt", action="store_true",
                    help="режим без ключа: напечатать промпт следующей части и путь для ответа модели среды (в журнал: degraded: env-model)")
    ap.add_argument("--apply", metavar="ФАЙЛ.json", help="применить ответ модели среды (JSON) к части, номер задаётся --part")
    ap.add_argument("--part", type=int, help="номер части для --apply")
    a = ap.parse_args(argv)

    if not SID_RE.match(a.source):
        print(f"Ошибка: «{a.source}» — не номер источника. Что сделать: укажите вид S-003 (список: sources.yaml проекта).", file=sys.stderr)
        return 2
    from tools.common import current_slug
    slug = a.project or current_slug()
    if not slug:
        print("Ошибка: проект не выбран. Что сделать: укажите -p <проект> или `python tools/project.py use <проект>`.", file=sys.stderr)
        return 2
    try:
        if a.apply:
            if not a.part:
                print("Ошибка: для --apply нужен --part N. Что сделать: добавьте номер части из подсказки --emit-prompt.", file=sys.stderr)
                return 2
            md, _ = _source(slug, a.source)
            qs = _questions(slug, a.question)
            parts = split_parts(md, PART_LIMIT)
            if 1 <= a.part <= len(parts) and state.is_done(slug, _aid(a.source, parts[a.part - 1], qs)):
                print(f"Часть {a.part} уже применена: ничего не записано.")
                return 0
            n = apply_result(slug, a.source, a.part, a.apply, a.question)
            left = [p.idx for p in parts if not state.is_done(slug, _aid(a.source, p, qs))]
            print(f"Часть {a.part} применена: новых утверждений {n}. Журнал: degraded: env-model.")
            if left:
                print(f"Осталось частей: {len(left)}. Что сделать: python tools/extract.py {a.source}{_qflags(a.question)} --emit-prompt")
            else:
                print(f"Все части готовы. Дальше: python tools/check.py --only 1,2,3,4 -p {slug}")
            return 0
        rep = extract_source(slug, a.source, questions=a.question, dry_run=a.dry_run, emit_prompt=a.emit_prompt)
    except llm.NoKeyError as e:
        print(f"{e}\nЧто сделать без ключа: `python tools/extract.py {a.source} --emit-prompt` и затем `--apply файл.json --part N` (модель среды вместо Yandex; в статусе красная строка).")
        return 3
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 2
    if a.dry_run or a.emit_prompt:
        return 0
    print(f"Источник {a.source}: частей {rep.parts_total} (из кеша {rep.parts_cached}), утверждений добавлено {rep.claims_added}, "
          f"цитат отброшено {rep.dropped_quotes}, табличных отброшено {rep.dropped_table_facts}, эскалаций {rep.escalations}, "
          f"стоимость {_fmt_rub(rep.rub)}.")
    if rep.pending:
        print(f"Без результата части: {', '.join(map(str, rep.pending))}. Что сделать: см. подсказки выше и `python tools/status.py`; затем запустите команду ещё раз — готовое не задвоится.")
        return 1
    print(f"Дальше: python tools/check.py --only 1,2,3,4 -p {slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
