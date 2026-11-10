# check.py: проверки 1–11 (цитата, числа, ячейки, ссылки, варианты, разделы стратегии, обещания, план проверки, основания, пробелы, ключи), подтверждение WARN, лимит итераций, отчёт; без него выдуманная цитата, пустая стратегия или утёкший ключ попадут к руководителю. Запираемый файл (У6).
"""Договорённости по типам утверждений (проверка 3):

* estimate — расчёт лежит в `calc/<C-id>.py` (соглашение задачи 18, например `calc/C-021.py`; последняя строка
  вывода скрипта `RESULT=<число> <единица>`). В поле locator утверждения можно продублировать `calc/<C-id>.py`.
  Задача 8 проверяет только существование файла внутри проекта; запуск и сверку значения делает задача 18.
* observation — locator вида `файл#зона` (например `S-007.png#top-right`); файл ищется в `materials/` проекта
  (или по пути от корня проекта) и должен существовать, зона не пуста. extracted_by `ux-observer` допустим.
* Коды выхода CLI: 0 — PASS, 1 — есть FAIL, 2 — есть WARN (FAIL нет), 3 — ошибка использования.
* табличный fact (locator `Лист!C14`) — `dims` и `value` точно равны заново разобранной ячейке, текст содержит их.

Документы проекта (проверки 5–10, У8) разбираются регулярками по заголовкам шаблонов `projects/_template/`:
* options.md — блоки `## O<n> · <вид> · Название`, строки `Возражения:` и маркированный список под ними;
* strategy.md — фиксированные заголовки (см. STRATEGY_SECTIONS); тезисы рекомендации `- Т<n>: … [C-…]`;
  обещания `- «…» → F-n`; функции продукта — `product.yaml` (`features`);
* интервью: респондент = поле `respondent` утверждения, иначе его источник (n=1 — один респондент);
* подтверждение WARN (`--confirm C-id --minutes N`) хранится в state.yaml (`confirmed`) вместе с отпечатком утверждения:
  правка цитаты или текста снимает подтверждение; минуты пишутся в state.human и log.jsonl (статья «человек»);
* лимит итераций: подряд идущие запуски с FAIL считаются в state.yaml (`check_fails`); 3-й подряд FAIL в шаге —
  `state.wait_human(point="check")` с блоком «Не прошло проверку: …»; успешный запуск счётчик сбрасывает.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rapidfuzz import fuzz  # noqa: E402

from tools import claims, ingest, lock, state, tables  # noqa: E402
from tools.common import (  # noqa: E402
    die, now_iso, project_path, read_text, read_yaml, setup_stdio, sha256_file, sha256_text, write_text_atomic,
)
from tools.log import event  # noqa: E402
from tools.numparse import count_negations, is_year, normalize_quote, num_match, parse_numbers  # noqa: E402

FUZZY_WARN = 92
CELL_RE = re.compile(r"^.+!\$?[A-Za-z]{1,3}\$?\d+$")
REF_RE = re.compile(r"\bC-\d+\b")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
REF_FILES = ("brief.md", "questions.md", "options.md", "critique.md", "strategy.md", "decisions.yaml", "product.yaml")
SECRET_RES = {
    "ключ Yandex (AQVN…)": re.compile(r"AQVN[A-Za-z0-9_\-]{16,}"),
    "ключ sk-…": re.compile(r"(?<![A-Za-z0-9_\-])sk-[A-Za-z0-9_\-]{16,}"),
    "заголовок Bearer": re.compile(r"Bearer\s+(?=[A-Za-z0-9._~+/=\-]*\d)[A-Za-z0-9._~+/=\-]{16,}"),
}
SKIP_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", "node_modules"}
SKIP_FILES = {".env"}


@dataclass
class Finding:
    level: str  # OK | WARN | FAIL
    check: int
    target: str
    msg: str
    hint: str = ""
    confirmed: bool = False  # WARN, подтверждённый человеком (`--confirm`); в счёт идёт как OK


def _f(level, check, target, msg, hint=""):
    return Finding(level, check, str(target), msg, hint)


# ---------- проверка 1: цитата ----------

def check_quote(c: dict, section_text: str) -> Finding:
    cid = c.get("id", "?")
    q, s = normalize_quote(c.get("quote") or ""), normalize_quote(section_text or "")
    if not q:
        return _f("FAIL", 1, cid, "цитата пустая", "Что сделать: вставь дословную цитату из источника.")
    if q in s:
        i = s.find(q)
        while i != -1:  # цитата, обрезанная сразу после «не», сама отрицаний не содержит
            before = s[:i].split()
            tok = before[-1].rstrip("\"')»”") if before else ""
            # «Нет. Рынок вырос…»: границей предложения считается только слово-ответ «нет/no» с точкой/!/?;
            # «не. выросла», «не… подтверждается», «does not. works» остаются отрицанием
            word = tok.strip(",;:()\"'«».!?…*")
            boundary = bool(tok) and tok[-1] in ".!?" and not tok.endswith("..") and word in ("нет", "no")
            if tok and count_negations(word) and not boundary:
                return _f("FAIL", 1, cid, f"перед цитатой в источнике стоит отрицание «{before[-1]}» (отрицание отрезано)",
                          "Что сделать: включи отрицание в цитату, чтобы смысл не изменился.")
            i = s.find(q, i + 1)
        return _f("OK", 1, cid, "цитата найдена дословно")
    al = fuzz.partial_ratio_alignment(q, s) if s else None
    if al is None or al.score < 50:
        return _f("FAIL", 1, cid, "цитаты нет в указанном разделе источника",
                  "Что сделать: проверь локатор и перепиши цитату дословно из источника.")
    window = s[al.dest_start:al.dest_end]
    if count_negations(q) != count_negations(window):
        return _f("FAIL", 1, cid, "число отрицаний (не/нет/без/ни/not/no) в цитате и в источнике различается",
                  "Что сделать: сверь смысл с источником и перепиши цитату дословно.")
    wn = parse_numbers(window)
    if any(not num_match(n, wn) for n in parse_numbers(q)):
        return _f("FAIL", 1, cid, "цитата почти совпала, но её числа отличаются от источника",
                  "Что сделать: перепиши цитату дословно, особенно числа.")
    if al.score >= FUZZY_WARN:
        return _f("WARN", 1, cid, f"цитата совпала не дословно (сходство {al.score:.0f}%)",
                  "Что сделать: исправь цитату дословно по источнику или подтверди вручную.")
    return _f("FAIL", 1, cid, f"цитата не найдена в разделе (лучшее сходство {al.score:.0f}%)",
              "Что сделать: проверь локатор и перепиши цитату дословно из источника.")


# ---------- проверка 2: числа ----------

def check_numbers(c: dict, quote: str, as_of: str | None) -> list[Finding]:
    cid = c.get("id", "?")
    fnums = parse_numbers(c.get("text") or "")
    qnums = parse_numbers(quote or "")
    year_as_of = int(as_of[:4]) if as_of and re.match(r"^\d{4}", str(as_of)) else None
    out: list[Finding] = []
    for n in fnums:
        if num_match(n, qnums):
            continue
        unit = f" {n.unit}" if n.unit and not is_year(n) else ""
        if is_year(n):
            other = sorted({int(x.value) for x in qnums if is_year(x)})
            if other:
                out.append(_f("FAIL", 2, cid, f"год {n.raw}: в цитате другой год ({', '.join(map(str, other))})",
                              "Что сделать: возьми год из цитаты."))
            elif year_as_of is None:
                out.append(_f("FAIL", 2, cid, f"год {n.raw} не в цитате, а у источника нет as_of",
                              "Что сделать: добавь год в цитату или проверь as_of в sources.yaml."))
            elif year_as_of != int(n.value):
                out.append(_f("FAIL", 2, cid, f"год {n.raw} не в цитате и не совпадает с as_of источника ({year_as_of})",
                              "Что сделать: возьми год из цитаты."))
            continue
        out.append(_f("FAIL", 2, cid, f"число «{n.raw}{unit}» не найдено в цитате с той же единицей",
                      "Что сделать: сверь число и единицу (%, п.п., ₽, ГБ…) с цитатой."))
    return out or [_f("OK", 2, cid, "числа и единицы совпадают с цитатой")]


# ---------- проверка 3: ячейки, расчёт, наблюдения ----------

def _flat(s: str) -> str:
    return re.sub(r"[   ]", "", str(s)).replace("−", "-").replace(",", ".").lower()


def check_table_fact(c: dict, src_path) -> Finding:
    cid = c.get("id", "?")
    try:
        cell = tables.get_cell(src_path, c.get("locator") or "")
    except ValueError as e:
        return _f("FAIL", 3, cid, str(e), "Что сделать: укажи адрес ячейки из materials/<S-id>.md.")
    if {str(k): str(v) for k, v in (c.get("dims") or {}).items()} != {str(k): str(v) for k, v in cell.dims.items()}:
        return _f("FAIL", 3, cid, f"dims не совпадают с ячейкой {cell.locator}: в таблице {cell.dims}",
                  "Что сделать: пересоздай факт `analyze.py cell`.")
    text = c.get("text") or ""
    nt = normalize_quote(text)
    for k, v in cell.dims.items():
        if normalize_quote(str(v)) not in nt:
            return _f("FAIL", 3, cid, f"в тексте факта нет значения {k}={v} из ячейки {cell.locator}",
                      "Что сделать: текст факта должен называть строку и столбец ячейки.")
    if not isinstance(cell.value, str):
        v = c.get("value")
        if v is None or isinstance(v, bool) or not math.isclose(float(v), float(cell.value), rel_tol=1e-9, abs_tol=1e-9):
            return _f("FAIL", 3, cid, f"value {v} не равно значению ячейки {cell.locator}: {cell.value}",
                      "Что сделать: пересоздай факт `analyze.py cell`.")
        cands = {_flat(tables.fmt_value(cell.value)), _flat(cell.value)}
        if not any(x in _flat(text) for x in cands):
            return _f("FAIL", 3, cid, f"в тексте факта нет значения ячейки {tables.fmt_value(cell.value)}",
                      "Что сделать: впиши в текст значение ячейки как есть.")
    return _f("OK", 3, cid, f"ячейка {cell.locator} совпала")


def _check_estimate(slug, c) -> Finding:
    cid = c.get("id", "?")
    p = (project_path(slug) / "calc" / f"{cid}.py")
    if not p.is_file():
        return _f("FAIL", 3, cid, f"у estimate нет расчёта calc/{cid}.py",
                  f"Что сделать: положи скрипт в calc/{cid}.py (последняя строка вывода `RESULT=<число> <единица>`).")
    return _f("OK", 3, cid, f"расчёт calc/{cid}.py на месте")


def _check_observation(slug, c) -> Finding:
    cid = c.get("id", "?")
    file, sep, zone = str(c.get("locator") or "").partition("#")
    if not sep or not zone.strip() or not file.strip():
        return _f("FAIL", 3, cid, "у observation нужен локатор «файл#зона» (например S-007.png#top-right)",
                  "Что сделать: укажи файл скриншота и зону.")
    root = project_path(slug).resolve()
    for base in (root / "materials", root):
        p = (base / file).resolve()
        if root in p.parents and p.is_file():
            return _f("OK", 3, cid, f"файл {file}, зона «{zone}»")
    return _f("FAIL", 3, cid, f"файла {file} нет в проекте", "Что сделать: положи скриншот в materials/ или поправь локатор.")


# ---------- проверка 4: ссылки ----------

def check_refs(slug) -> list[Finding]:
    root = project_path(slug)
    status = {c["id"]: c.get("status") for c in claims.load(slug)}
    out: list[Finding] = []
    for name in REF_FILES:
        p = root / name
        if not p.is_file():
            continue
        text = COMMENT_RE.sub("", p.read_text(encoding="utf-8"))
        if name.endswith(".yaml"):
            text = re.sub(r"(?m)#.*$", "", text)  # примеры [C-001] в комментариях шаблонов не ссылки
        for cid in sorted(set(REF_RE.findall(text))):
            st = status.get(cid)
            if st is None:
                out.append(_f("FAIL", 4, cid, f"{name}: ссылка на несуществующее утверждение",
                              "Что сделать: убери ссылку или добавь утверждение (`claims.py list`)."))
            elif st in ("superseded", "retracted"):
                out.append(_f("FAIL", 4, cid, f"{name}: утверждение имеет статус {st}",
                              "Что сделать: замени ссылку на действующее утверждение."))
    return out or [_f("OK", 4, str(root), "ссылки [C-…] целы")]


# ---------- проверка 11 (часть): ключи ----------

def check_secrets(root) -> list[Finding]:
    root = Path(root)
    out: list[Finding] = []
    files = [root] if root.is_file() else sorted(root.rglob("*"))
    for p in files:
        if not p.is_file() or p.name in SKIP_FILES or any(part in SKIP_DIRS for part in p.parts):
            continue
        shown = p.relative_to(root).as_posix() if root.is_dir() else p.name
        try:
            with p.open("rb") as fh:  # построчно: большие файлы не пропускаем и не грузим целиком
                if b"\x00" in fh.read(8192):
                    continue
                fh.seek(0)
                for i, raw in enumerate(fh, 1):
                    line = raw.decode("utf-8", errors="ignore")
                    for label, rx in SECRET_RES.items():
                        if rx.search(line):  # сам ключ в сообщение не пишем
                            out.append(_f("FAIL", 11, shown, f"строка {i}: похоже на {label}",
                                          "Что сделать: удали секрет из файла, перевыпусти ключ, храни только в .env."))
        except OSError:
            continue
    return out or [_f("OK", 11, str(root), "ключей не найдено")]


def check_lock(root=None) -> list[Finding]:
    """Проверка 11 (часть): запертые файлы совпадают с rules.lock."""
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    problems = lock.verify(root)
    if not problems:
        return [_f("OK", 11, "rules.lock", "правила совпадают с rules.lock")]
    return [_f("FAIL", 11, "rules.lock", "правила не совпадают с rules.lock: " + "; ".join(problems),
               "Что сделать: если правка осознанная — `python tools/lock.py --update --reason \"…\"`, иначе верни файлы.")]


# ---------- проверки 5–10: документы проекта (У8: заголовки и формат разбираются регулярками, не LLM) ----------

OPT_HEAD_RE = re.compile(r"^##\s+(O\d+)\s*(?:[·•|:–—-]\s*([A-Za-z_]+))?\s*(?:[·•|:–—-]\s*(.*?))?\s*$")
OPT_LABELS = ("суть", "что даёт", "чего стоит", "возражения", "что заставит передумать", "выбрано")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
BULLET_RE = re.compile(r"^\s*[-*•]\s+(.*)$")
THESIS_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:(?:\*\*)?[ТT](\d+)(?:\*\*)?\s*(?:[:.)]|[—–-])|(\d+)[.)]\s)\s*(.*)$")
PROMISE_RE = re.compile(r"^\s*[-*]\s*[«\"]?(.+?)[»\"]?\s*(?:→|->)\s*\*{0,2}(F-\d+)\*{0,2}(?:\s*[(,;—–].*)?\s*[.;]?\s*$")
UNKNOWN_RE = re.compile(r"не знаем.+потому что.+узнать", re.DOTALL)
FEATURE_STATUSES = ("exists", "planned")
STRONG_TYPES = ("fact", "observation", "estimate", "interview")  # основание тезиса, не написанное агентом и не синтетика
TIME_WORDS = re.compile(r"недел|месяц|мес\b|квартал|кв\b|день|дн|год|лет|сутки|\d")
# (уровень, заголовок, лист): лист — раздел без подразделов, его содержимое должно быть непустым
STRATEGY_SECTIONS = (
    (2, "Рекомендация", True),
    (2, "Продуктовая стратегия", False),
    (3, "Аудитория и её задача", True), (3, "Альтернативы", True), (3, "Выбранное направление", True),
    (3, "Осознанные отказы", True), (3, "Польза, затраты и доходы", True),
    (2, "Коммуникационная стратегия", False),
    (3, "Аудитория и ситуация", True), (3, "Барьер понимания или выбора", True),
    (3, "Ключевое сообщение и его подтверждение", True), (3, "Роли каналов", True),
    (3, "Обещания → функции продукта", True),
    (2, "План проверки", False),
    (3, "Ожидаемое изменение", True), (3, "База сравнения", True), (3, "Срок наблюдения", True),
    (3, "Нежелательные последствия", True),
    (2, "Чего мы не знаем", True),
    (2, "Источники", True),
)
PLAN_PARTS = ("Ожидаемое изменение", "База сравнения", "Срок наблюдения", "Нежелательные последствия")
REC, PROMISES, UNKNOWNS = "Рекомендация", "Обещания → функции продукта", "Чего мы не знаем"


def _norm_title(t: str) -> str:
    t = t.lower().replace("ё", "е").replace("->", "→")
    return re.sub(r"\s+", " ", t).strip(" :.")


def _doc(slug, name: str) -> str | None:
    p = project_path(slug) / name
    return COMMENT_RE.sub("", read_text(p)) if p.is_file() else None


def _sections(text: str) -> list[dict]:
    """Разбор md на разделы: {level, title, norm, lines (до следующего заголовка), sub (до заголовка того же или старшего уровня)}."""
    lines = text.splitlines()
    heads = []
    fence = False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else HEAD_RE.match(ln)
        if m:
            heads.append((i, len(m.group(1)), m.group(2)))
    out = []
    for k, (i, lvl, title) in enumerate(heads):
        nxt = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        end = next((j for j, l2, _ in heads[k + 1:] if l2 <= lvl), len(lines))
        out.append({"level": lvl, "title": title, "norm": _norm_title(title),
                    "lines": lines[i + 1:nxt], "sub": lines[i + 1:end]})
    return out


def _find(secs, level: int, title: str) -> dict | None:
    n = _norm_title(title)
    return next((s for s in secs if s["level"] == level and s["norm"] == n), None)


def _body(lines) -> str:
    return "\n".join(lines).strip()


def _missing_doc(check: int, name: str) -> list[Finding]:
    return [_f("FAIL", check, name, f"файла {name} нет в проекте", f"Что сделать: создай {name} по шаблону projects/_template/{name}.")]


def _claim_status(slug) -> dict[str, str]:
    return {c["id"]: c.get("status") for c in claims.load(slug)}


def _live(status: dict, cid: str) -> bool:
    return status.get(cid) in ("active", "disputed")


def _options_blocks(text: str) -> list[dict]:
    blocks: list[dict] = []
    for ln in text.splitlines():
        if ln.startswith("## "):
            m = OPT_HEAD_RE.match(ln)
            blocks.append({"id": m.group(1) if m else None, "kind": (m.group(2) or "") if m else "",
                           "title": (m.group(3) or "") if m else "", "lines": []})
        elif blocks:
            blocks[-1]["lines"].append(ln)
    return [b for b in blocks if b["id"]]


def _objections(lines) -> list[str]:
    items: list[str] = []
    on = False
    for ln in lines:
        low = ln.replace("*", "").strip().lower()
        label = next((lb for lb in OPT_LABELS if low.startswith(lb) and low[len(lb):].lstrip().startswith(":")), None)
        if label:
            on = label == "возражения"
            continue
        if not on:
            continue
        m = BULLET_RE.match(ln)
        if m:
            items.append(m.group(1).strip())
        elif ln.strip() and items:
            items[-1] += " " + ln.strip()
    return [x for x in items if x]


def check_options(slug) -> list[Finding]:
    """Проверка 5: ≥3 вариантов, среди них status_quo и close; у каждого ≥2 возражения, ≥1 со ссылкой на живое утверждение."""
    text = _doc(slug, "options.md")
    if text is None:
        return _missing_doc(5, "options.md")
    blocks = _options_blocks(text)
    status = _claim_status(slug)
    out: list[Finding] = []
    if len(blocks) < 3:
        out.append(_f("FAIL", 5, "options.md", f"вариантов меньше 3 (найдено {len(blocks)})",
                      "Что сделать: опиши ≥3 варианта блоками `## O1 · status_quo · Название` (формат в шаблоне options.md)."))
    kinds = {b["kind"] for b in blocks}
    for need, what in (("status_quo", "«оставить как есть»"), ("close", "«закрыть направление»")):
        if need not in kinds:
            out.append(_f("FAIL", 5, "options.md", f"нет обязательного варианта {need} {what}",
                          f"Что сделать: добавь вариант `## O<n> · {need} · …` с ценой и условиями."))
    for b in blocks:
        obj = _objections(b["lines"])
        if len(obj) < 2:
            out.append(_f("FAIL", 5, b["id"], f"возражений {len(obj)}, нужно ≥2",
                          "Что сделать: под «Возражения:» добавь строки `- В1: …`, `- В2: … [C-001]`."))
            continue
        refs = [r for o in obj for r in REF_RE.findall(o)]
        if not any(_live(status, r) for r in refs):
            bad = f" (ссылки {', '.join(sorted(set(refs)))} не ведут на действующее утверждение)" if refs else ""
            out.append(_f("FAIL", 5, b["id"], f"нет возражения со ссылкой на существующее утверждение [C-…]{bad}",
                          "Что сделать: подкрепи хотя бы одно возражение действующим утверждением (`claims.py search`)."))
    return out or [_f("OK", 5, "options.md", f"вариантов {len(blocks)}, status_quo и close есть, возражения в порядке")]


def check_strategy_sections(slug) -> list[Finding]:
    """Проверка 6: все заголовки шаблона strategy.md на своих уровнях, листовые разделы не пусты."""
    text = _doc(slug, "strategy.md")
    if text is None:
        return _missing_doc(6, "strategy.md")
    secs = _sections(text)
    out: list[Finding] = []
    for level, title, leaf in STRATEGY_SECTIONS:
        s = _find(secs, level, title)
        if s is None:
            other = next((x for x in secs if x["norm"] == _norm_title(title)), None)
            why = f"заголовок есть, но уровень {other['level']} вместо {level}" if other else "раздела нет"
            out.append(_f("FAIL", 6, "strategy.md", f"{'#' * level} {title}: {why}",
                          "Что сделать: верни заголовок шаблона как есть (проверка разбирает их регулярками)."))
        elif leaf and not _body(s["lines"]):
            out.append(_f("FAIL", 6, "strategy.md", f"{'#' * level} {title}: раздел пуст",
                          "Что сделать: заполни раздел (см. playbooks/5-strategy.md)."))
    return out or [_f("OK", 6, "strategy.md", "все разделы шаблона на месте и заполнены")]


def _features(slug) -> tuple[dict[str, dict], str]:
    p = project_path(slug) / "product.yaml"
    if not p.is_file():
        return {}, "product.yaml нет"
    try:
        data = read_yaml(p) or {}
    except yaml.YAMLError:
        return {}, "product.yaml не разобран (ошибка YAML)"
    feats = data.get("features") if isinstance(data, dict) else None
    out = {}
    for f in feats or []:
        if isinstance(f, dict) and f.get("id"):
            out[str(f["id"])] = f
    return out, ""


def check_promises_static(slug) -> list[Finding]:
    """Проверка 7: у каждого обещания «…» → F-n есть функция в product.yaml; для planned указан срок."""
    text = _doc(slug, "strategy.md")
    if text is None:
        return _missing_doc(7, "strategy.md")
    sec = _find(_sections(text), 3, PROMISES)
    if sec is None:
        return [_f("FAIL", 7, "strategy.md", f"нет раздела «{PROMISES}»", "Что сделать: верни заголовок шаблона.")]
    feats, err = _features(slug)
    out: list[Finding] = []
    if err:
        out.append(_f("FAIL", 7, "product.yaml", err, "Что сделать: заполни product.yaml по формату шаблона."))
    n = 0
    for ln in sec["lines"]:
        if not ln.strip():
            continue
        is_item = bool(BULLET_RE.match(ln)) or "→" in ln or "->" in ln
        if not is_item:
            continue  # вводная строка-проза
        m = PROMISE_RE.match(ln)
        if not m:
            out.append(_f("FAIL", 7, "strategy.md", f"строка не в формате «…» → F-n: {ln.strip()[:60]}",
                          "Что сделать: перепиши как `- «обещание» → F-1`; нет функции — убери обещание или заведи planned со сроком."))
            continue
        n += 1
        fid = m.group(2)
        f = feats.get(fid)
        if f is None:
            if not err:
                out.append(_f("FAIL", 7, fid, f"обещание «{m.group(1)[:40]}»: функции {fid} нет в product.yaml",
                              "Что сделать: добавь функцию в product.yaml или убери обещание."))
        elif f.get("status") not in FEATURE_STATUSES:
            out.append(_f("FAIL", 7, fid, f"{fid}: status должен быть exists или planned, а не {f.get('status')!r}",
                          "Что сделать: поправь status в product.yaml."))
        elif f["status"] == "planned" and not str(f.get("available_from") or "").strip():
            out.append(_f("FAIL", 7, fid, f"{fid} planned, но не указан срок (available_from)",
                          "Что сделать: впиши available_from (например 2027-Q1) или убери обещание."))
    if n == 0 and not out:
        out.append(_f("FAIL", 7, "strategy.md", f"в разделе «{PROMISES}» нет ни одного обещания",
                      "Что сделать: добавь строки `- «обещание» → F-1` (или заведи функцию и обещание)."))
    return out or [_f("OK", 7, "strategy.md", f"обещаний {n}, у всех есть функция")]


def check_test_plan(slug) -> list[Finding]:
    """Проверка 8: план проверки — метрика и ожидаемое изменение, база, срок, нежелательные последствия (guardrail)."""
    text = _doc(slug, "strategy.md")
    if text is None:
        return _missing_doc(8, "strategy.md")
    secs = _sections(text)
    out: list[Finding] = []
    for title in PLAN_PARTS:
        s = _find(secs, 3, title)
        body = _body(s["lines"]) if s else ""
        if s is None:
            out.append(_f("FAIL", 8, "strategy.md", f"в плане проверки нет части «{title}»", "Что сделать: верни заголовок шаблона и заполни (methods/test-plan.md)."))
        elif len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]", body)) < 10:
            out.append(_f("FAIL", 8, "strategy.md", f"часть «{title}» пуста или заглушка",
                          "Что сделать: опиши конкретно (метрика, число, срок, guardrail)."))
        elif title == "Ожидаемое изменение" and not re.search(r"\d", body):
            out.append(_f("FAIL", 8, "strategy.md", f"в части «{title}» нет числа",
                          "Что сделать: назови метрику и целевое значение числом с единицей."))
        elif title == "Срок наблюдения" and not TIME_WORDS.search(body.lower()):
            out.append(_f("FAIL", 8, "strategy.md", f"в части «{title}» нет срока",
                          "Что сделать: укажи срок (например «3 месяца после запуска»)."))
    return out or [_f("OK", 8, "strategy.md", "план проверки: изменение, база, срок и нежелательные последствия указаны")]


def _loc_key(loc) -> str:
    loc = str(loc or "").strip()
    if "!" in loc:
        sh, _, ref = loc.rpartition("!")
        return f"{sh}!{ref.replace('$', '').upper()}"
    return loc


def _suspicious(slug) -> dict[str, set[str]]:
    return {s["id"]: {_loc_key(x) for x in (s.get("suspicious") or [])} for s in ingest._load_sources(slug)}


def _is_suspicious(c: dict, susp: dict[str, set[str]]) -> bool:
    return bool(c.get("source") and c.get("locator") and _loc_key(c["locator"]) in susp.get(c["source"], set()))


def _theses(section_lines) -> list[tuple[str, str]]:
    """Тезисы «- Т1: …», «1. …», «Т1 — …»; любая другая строка со ссылкой [C-…] тоже проверяется как тезис."""
    out: list[list[str]] = []
    for ln in section_lines:
        m = THESIS_RE.match(ln)
        if m:
            out.append([f"Т{m.group(1) or m.group(2)}", m.group(3).strip()])
        elif out and ln.strip() and ln[:1].isspace() and not BULLET_RE.match(ln):
            out[-1][1] += " " + ln.strip()
        elif REF_RE.search(ln):
            out.append([f"строка «{ln.strip()[:30]}»", ln.strip()])
    return [(a, b) for a, b in out]


def check_basis(slug) -> list[Finding]:
    """Проверка 9: тезис рекомендации не опирается только на synthetic, только на interview одного респондента или только на suspicious."""
    text = _doc(slug, "strategy.md")
    if text is None:
        return _missing_doc(9, "strategy.md")
    sec = _find(_sections(text), 2, REC)
    theses = _theses(sec["sub"]) if sec else []
    if not theses:
        return [_f("FAIL", 9, "strategy.md", f"в разделе «{REC}» нет тезисов вида «- Т1: … [C-…]»",
                   "Что сделать: оформи рекомендацию тезисами со ссылками на утверждения.")]
    by_id = {c["id"]: c for c in claims.load(slug)}
    susp = _suspicious(slug)
    out: list[Finding] = []
    for tid, body in theses:
        cs = [by_id[r] for r in dict.fromkeys(REF_RE.findall(body)) if r in by_id and _live({r: by_id[r].get("status")}, r)]
        if not cs:
            out.append(_f("FAIL", 9, tid, "у тезиса нет ссылок на действующие утверждения [C-…]",
                          "Что сделать: подкрепи тезис утверждением (`claims.py search`) или убери."))
            continue
        strong = [c for c in cs if c.get("type") in STRONG_TYPES and not _is_suspicious(c, susp)]
        weak = any(c.get("type") == "synthetic" or _is_suspicious(c, susp) for c in cs)
        if weak and not strong:
            kinds = []
            if any(c.get("type") == "synthetic" for c in cs):
                kinds.append("synthetic")
            if any(_is_suspicious(c, susp) for c in cs):
                kinds.append("абзацы suspicious")
            out.append(_f("FAIL", 9, tid, f"тезис опирается только на {' и '.join(kinds)}",
                          "Что сделать: найди подтверждение в реальном источнике или пометь тезис как гипотезу."))
        elif strong and all(c.get("type") == "interview" for c in strong) and \
                len({c.get("respondent") or c.get("source") or c["id"] for c in strong}) < 2:
            out.append(_f("FAIL", 9, tid, "тезис опирается только на interview одного респондента (n=1)",
                          "Что сделать: добавь второго респондента или другой тип источника, либо пометь тезис как гипотезу."))
    return out or [_f("OK", 9, "strategy.md", f"тезисов {len(theses)}, у каждого есть основание кроме synthetic, n=1 и suspicious")]


def check_unknowns(slug) -> list[Finding]:
    """Проверка 10: «Чего мы не знаем» не пусто, каждый пункт «Не знаем X, потому что Y. Узнать так: Z»."""
    text = _doc(slug, "strategy.md")
    if text is None:
        return _missing_doc(10, "strategy.md")
    sec = _find(_sections(text), 2, UNKNOWNS)
    if sec is None:
        return [_f("FAIL", 10, "strategy.md", f"нет раздела «{UNKNOWNS}»", "Что сделать: верни заголовок шаблона.")]
    items: list[str] = []
    for ln in sec["sub"]:
        m = BULLET_RE.match(ln)
        if m:
            items.append(m.group(1).strip())
        elif ln.strip():
            if items and ln[:1].isspace():
                items[-1] += " " + ln.strip()
            else:
                items.append(ln.strip())
    if not items:
        return [_f("FAIL", 10, "strategy.md", f"раздел «{UNKNOWNS}» пуст",
                   "Что сделать: перечисли, чего не знаем: «Не знаем X, потому что Y. Узнать так: Z».")]
    out = [_f("FAIL", 10, "strategy.md", f"пункт не в формате «Не знаем X, потому что Y. Узнать так: Z»: {it[:50]}",
              "Что сделать: перепиши пункт в этом формате.")
           for it in items if not UNKNOWN_RE.search(it.lower().replace("ё", "е"))]
    return out or [_f("OK", 10, "strategy.md", f"пробелов указано {len(items)}")]


# ---------- подтверждение WARN, лимит итераций, отчёт ----------

MAX_ITERATIONS = 3
CHECKS = tuple(range(1, 12))


def _fingerprint(c: dict) -> str:
    return sha256_text(json.dumps([c.get(k) for k in ("type", "text", "source", "locator", "quote")], ensure_ascii=False))[:16]


def _apply_confirmations(slug, findings: list[Finding]) -> list[Finding]:
    conf = state.load(slug).get("confirmed") or {}
    if not conf:
        return findings
    by_id = {c["id"]: c for c in claims.load(slug)}
    out = []
    for f in findings:
        c = by_id.get(f.target)
        rec = conf.get(f.target)
        if f.level == "WARN" and c and rec and rec.get("fp") == _fingerprint(c):
            f = Finding("OK", f.check, f.target, f"WARN подтверждён человеком ({rec.get('minutes')} мин): {f.msg}", "", True)
        out.append(f)
    return out


def confirm(slug, cid: str, minutes: float) -> bool:
    """Подтверждает WARN по утверждению: сохраняет отпечаток, минуты идут в статью «человек». False — уже подтверждено."""
    c = claims.get(slug, cid)
    st = state.load(slug)
    conf = st.setdefault("confirmed", {})
    if conf.get(cid, {}).get("fp") == _fingerprint(c):
        return False
    conf[cid] = {"fp": _fingerprint(c), "minutes": minutes, "at": now_iso()}
    summary = f"check: подтверждён WARN по {cid}"
    st["human"].append({"point": "check-confirm", "summary": summary, "minutes": minutes, "at": now_iso()})
    state.save(slug, st)
    event(slug, "human", point="check-confirm", summary=summary, minutes=minutes)
    return True


def _verdict(findings: list[Finding]) -> int:
    return 1 if any(f.level == "FAIL" for f in findings) else 2 if any(f.level == "WARN" for f in findings) else 0


def _track_iterations(slug, findings: list[Finding], ran: set[int]) -> int:
    """Считает подряд идущие запуски с FAIL в текущем шаге. Возвращает номер итерации (0 — FAIL нет)."""
    st = state.load(slug)
    step = (st.get("step") or {}).get("n", 0)
    prev = st.get("check_fails") or {}
    failed = sorted({f.check for f in findings if f.level == "FAIL"})
    if failed:
        same = prev.get("step") == step
        count = (prev.get("count", 0) if same else 0) + 1
        checks = sorted(set(prev.get("checks", []) if same else []) | set(failed))
        st["check_fails"] = {"step": step, "count": count, "checks": checks}
        state.save(slug, st)
        if count >= MAX_ITERATIONS and (count == MAX_ITERATIONS or (st.get("waiting") or {}).get("point") != "check"):
            lines = [f"- п.{f.check} {f.target}: {f.msg}" for f in findings if f.level == "FAIL"][:15]
            state.wait_human(slug, "check", f"Не прошло проверку: {len(lines)} замечаний после {count} итераций исправления.\n" + "\n".join(lines))
        return count
    if prev and set(prev.get("checks", [])) <= ran:
        st.pop("check_fails", None)  # ожидание человека (point=check) снимает только state.resolve_human
        state.save(slug, st)
    return 0


def write_report(slug, findings: list[Finding], ran: set[int], iteration: int, skipped: str = "") -> Path:
    code = _verdict(findings)
    verdict = {0: "PASS", 1: "FAIL", 2: "WARN (есть неподтверждённые предупреждения)"}[code]
    lines = ["# Отчёт проверки (check.py)", "", f"Проект: {project_path(slug).name}. Запуск: {now_iso()}.",
             f"Проверки: {', '.join(map(str, sorted(ran)))}. Итог: **{verdict}**, код выхода {code}.", ""]
    fl = [f for f in findings if f.level == "FAIL"]
    wl = [f for f in findings if f.level == "WARN"]
    cl = [f for f in findings if f.confirmed]
    lines.append("## Не прошло (FAIL)")
    lines += [f"- п.{f.check} {f.target}: {f.msg} {f.hint}".rstrip() for f in fl] or ["- нет"]
    lines += ["", "## Предупреждения (WARN): блокируют стратегию до подтверждения"]
    lines += [f"- п.{f.check} {f.target}: {f.msg} Подтвердить: `python tools/check.py --confirm {f.target} --minutes <минуты>`"
              if re.fullmatch(r"C-\d+", f.target) else f"- п.{f.check} {f.target}: {f.msg}" for f in wl] or ["- нет"]
    lines += ["", "## Подтверждено человеком"] + ([f"- п.{f.check} {f.target}: {f.msg}" for f in cl] or ["- нет"])
    lines += ["", "## По проверкам", "", "| п. | OK | WARN | FAIL |", "|---|---|---|---|"]
    for n in sorted(ran):
        fs = [f for f in findings if f.check == n]
        lines.append(f"| п.{n} | {sum(f.level == 'OK' for f in fs)} | {sum(f.level == 'WARN' for f in fs)} | {sum(f.level == 'FAIL' for f in fs)} |")
    lines += ["", "## Итерации исправления",
              f"Подряд запусков с FAIL: {iteration} из {MAX_ITERATIONS}."
              + (" Лимит исчерпан: решение за человеком (state.yaml, waiting)." if iteration >= MAX_ITERATIONS else "")]
    if iteration >= MAX_ITERATIONS or (state.load(slug).get("waiting") or {}).get("point") == "check":
        lines += ["", "Лимит итераций был исчерпан: ожидание человека не снимается автоматически (`state.resolve_human`)."]
    if skipped:
        lines += ["", skipped]
    p = project_path(slug) / "check-report.md"
    write_text_atomic(p, "\n".join(lines) + "\n")
    return p


# ---------- запуск ----------

def _is_cell_claim(c) -> bool:
    return bool(CELL_RE.match(str(c.get("locator") or "")))


def _table_path(slug, sources, c):
    src = next((s for s in sources if s["id"] == c.get("source")), None)
    if src is None or src.get("kind") not in ("table", "xlsx", "csv"):
        return None, f"источник {c.get('source')} не найден или не таблица"
    ext = src.get("ext") or src["kind"]  # kind: table + ext (xlsx/xlsm/csv); старый формат — kind=xlsx|csv
    p = project_path(slug) / "materials" / f"{src['id']}.{ext}"
    if not p.is_file() or sha256_file(p) != src["sha256"]:
        return None, f"оригинал {src['id']} отсутствует или изменён"
    return p, ""


def _claim_findings(slug, c, sources, want) -> list[Finding]:
    cid, t = c["id"], c.get("type")
    out: list[Finding] = []
    errs = claims.validate(c)
    if errs:  # fact без источника или от агента не должен молча проходить мимо проверок
        return [_f("FAIL", 1, cid, "утверждение не проходит правила реестра: " + "; ".join(errs),
                   f"Что сделать: исправь запись (`claims.py show {cid}`) или отзови её.")] if 1 in want else []
    src = next((s for s in sources if s["id"] == c.get("source")), None)
    if t == "estimate":
        if 3 in want:
            out.append(_check_estimate(slug, c))
        if _is_cell_claim(c) and c.get("dims") is not None and 3 in want:
            p, why = _table_path(slug, sources, c)
            out.append(check_table_fact(c, p) if p else _f("FAIL", 3, cid, why, "Что сделать: добавь таблицу заново через ingest.py."))
        return out
    if t == "observation":
        return [_check_observation(slug, c)] if 3 in want else []
    if not (c.get("source") and c.get("locator") and c.get("quote")):
        return out  # hypothesis/conclusion/forecast без источника проверкам 1–3 не подлежат
    if 1 in want and src is not None and _loc_key(c["locator"]) in {_loc_key(x) for x in (src.get("suspicious") or [])}:
        out.append(_f("WARN", 1, cid, f"утверждение опирается на фрагмент {c['locator']} источника {c['source']}, помеченный suspicious (возможная инъекция)",
                      "Что сделать: найди подтверждение в чистом фрагменте или проверь вручную и подтверди `check.py --confirm <id> --minutes N`."))
    if _is_cell_claim(c):
        if 3 in want:
            p, why = _table_path(slug, sources, c)
            out.append(check_table_fact(c, p) if p else _f("FAIL", 3, cid, why, "Что сделать: добавь таблицу заново через ingest.py."))
        return out
    try:
        section = ingest.section(slug, c["source"], c["locator"])
    except ValueError as e:
        return [_f("FAIL", 1, cid, str(e), "Что сделать: поправь source/locator утверждения.")] if 1 in want else []
    if 1 in want:
        out.append(check_quote(c, section))
    if 2 in want and t == "fact":
        out += check_numbers(c, c["quote"], (src or {}).get("as_of"))
    return out


def run(slug, only=None, *, apply_confirm: bool = True) -> list[Finding]:
    """only — набор номеров проверок (1–11); None — все. Подтверждённые человеком WARN идут как OK (confirmed=True)."""
    want = set(only) if only else set(CHECKS)
    sources = ingest._load_sources(slug)
    out: list[Finding] = []
    if want & {1, 2, 3}:
        for c in claims.active(slug):
            out += _claim_findings(slug, c, sources, want)
    if 4 in want:
        out += check_refs(slug)
    for n, fn in ((5, check_options), (6, check_strategy_sections), (7, check_promises_static),
                  (8, check_test_plan), (9, check_basis), (10, check_unknowns)):
        if n in want:
            out += fn(slug)
    if 11 in want:
        out += check_secrets(project_path(slug))
        out += check_lock()
    return _apply_confirmations(slug, out) if apply_confirm else out


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # ошибка использования — код 3, чтобы не путать с FAIL (1) и WARN (2)
        self.print_usage(sys.stderr)
        print(f"Ошибка: {message}. Что сделать: `python tools/check.py --help`.", file=sys.stderr)
        sys.exit(3)


def main(argv=None) -> int:
    setup_stdio()
    ap = _Parser(description="Проверка проекта: цитаты, числа с единицами, ячейки таблиц, ссылки (1–4), варианты (5), разделы стратегии (6), "
                             "обещания и функции (7), план проверки (8), основания тезисов (9), пробелы (10), ключи и правила (11). "
                             "Пишет check-report.md в папку проекта.",
                 epilog="Коды выхода: 0 — всё прошло (PASS), 1 — есть FAIL, 2 — есть неподтверждённые WARN, 3 — ошибка использования. "
                        "Исправлять и перезапускать можно не больше 3 итераций: после 3-го подряд FAIL проект ждёт человека "
                        "(блок «Не прошло проверку: …»). На ранних шагах проверки документов пропускаются с пометкой «пропущено».")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    ap.add_argument("--only", help="номера проверок через запятую, например 1,5; с --only выполняются всегда. Без --only: все 1–11, но п.5 пропускается "
                                  "на шагах до 4, п.6–10 на шагах до 5 (в выводе и отчёте строка «пропущено»)")
    ap.add_argument("--confirm", action="append", metavar="C-014",
                    help="подтвердить WARN по утверждению (человек сверил цитату вручную); нужен --minutes; можно повторять")
    ap.add_argument("--minutes", type=float, help="сколько минут ушло на подтверждение (идут в статью «человек»)")
    ap.add_argument("--repo", action="store_true", help="для проверки 11 просканировать и всю папку агента, а не только проект")
    a = ap.parse_args(argv)
    try:
        only = {int(x) for x in a.only.split(",") if x.strip()} if a.only else None
    except ValueError:
        die("--only: нужны номера проверок через запятую. Что сделать: например `--only 1,5`.", code=3)
    if only and not only <= set(CHECKS):
        die("--only: есть проверки 1–11. Что сделать: укажи номера из этого диапазона.", code=3)
    try:
        slug = project_path(a.project).name
    except SystemExit:  # project_path уже объяснил, что делать; для CLI это ошибка использования
        sys.exit(3)
    if a.confirm:
        if a.minutes is None or not math.isfinite(a.minutes) or a.minutes < 0:
            die("--confirm требует --minutes <минуты ≥0>. Что сделать: например `--confirm C-014 --minutes 2`.", code=3)
        raw = run(slug, {1, 2, 3}, apply_confirm=False)
        for cid in a.confirm:
            try:
                c = claims.get(slug, cid)
            except KeyError as e:
                die(str(e.args[0]), code=3)
            if not any(f.level == "WARN" and f.target == cid for f in raw):
                if (state.load(slug).get("confirmed") or {}).get(cid, {}).get("fp") == _fingerprint(c):
                    print(f"{cid}: уже подтверждено, минуты не добавлены.")
                    continue
                die(f"у {cid} нет предупреждения WARN, подтверждать нечего. Что сделать: `python tools/check.py` и возьми id из строки [WARN].", code=3)
            print(f"{cid}: WARN подтверждён, {a.minutes:g} мин записано в журнал." if confirm(slug, cid, a.minutes)
                  else f"{cid}: уже подтверждено, минуты не добавлены.")
    ran = set(only) if only else set(CHECKS)
    skipped = ""
    if only is None:  # без --only: проверки документов ждут своего шага (ранний запуск не должен краснеть)
        n_step = (state.load(slug).get("step") or {}).get("n", 0)
        cut = {n for n in range(5, 11) if n_step < (4 if n == 5 else 5)}
        if cut:
            ran -= cut
            skipped = (f"пропущено: проверки {', '.join(map(str, sorted(cut)))}: шаг {n_step} (нужны с шага 4 для п.5 и с шага 5 для п.6–10). "
                       "Это не подтверждение стратегии: перед точкой 3 запусти без пропусков (`--only 5,6,7,8,9,10`).")
    findings = run(slug, ran)
    if a.repo and (only is None or 11 in only):
        findings += check_secrets(Path(__file__).resolve().parent.parent)
    iteration = _track_iterations(slug, findings, ran)
    report_path = write_report(slug, findings, ran, iteration, skipped)
    if skipped:
        print(skipped)
    for f in findings:
        if f.level != "OK":
            print(f"[{f.level}] п.{f.check} {f.target}: {f.msg}" + (f" {f.hint}" if f.hint else ""))
    n = {lv: sum(1 for f in findings if f.level == lv) for lv in ("OK", "WARN", "FAIL")}
    print(f"Итого: OK {n['OK']}, WARN {n['WARN']}, FAIL {n['FAIL']}. Отчёт: {report_path.parent.name}/{report_path.name}.")
    if iteration >= MAX_ITERATIONS:
        print(f"Лимит {MAX_ITERATIONS} итераций исправления исчерпан. Что сделать: покажи человеку блок «Не прошло проверку: …» "
              "(он записан в state.yaml) и не перезапускай проверку, пока он не решит.")
    elif iteration:
        print(f"Итерация исправления {iteration} из {MAX_ITERATIONS}.")
    return _verdict(findings)


if __name__ == "__main__":
    sys.exit(main())
