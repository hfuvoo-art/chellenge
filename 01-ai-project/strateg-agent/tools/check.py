# check.py: проверки 1–4 и 11 (цитата, числа с единицами, ячейки/расчёт/наблюдение, ссылки C-…, ключи); без него выдуманная цитата, не та строка таблицы или утёкший ключ попадут в стратегию. Запираемый файл (У6).
"""Договорённости по типам утверждений (проверка 3):

* estimate — расчёт лежит в `calc/<C-id>.py` (соглашение задачи 18, например `calc/C-021.py`; последняя строка
  вывода скрипта `RESULT=<число> <единица>`). В поле locator утверждения можно продублировать `calc/<C-id>.py`.
  Задача 8 проверяет только существование файла внутри проекта; запуск и сверку значения делает задача 18.
* observation — locator вида `файл#зона` (например `S-007.png#top-right`); файл ищется в `materials/` проекта
  (или по пути от корня проекта) и должен существовать, зона не пуста. extracted_by `ux-observer` допустим.
* Коды выхода CLI: 0 — PASS, 1 — есть FAIL, 2 — есть WARN (FAIL нет), 3 — ошибка использования.
* табличный fact (locator `Лист!C14`) — `dims` и `value` точно равны заново разобранной ячейке, текст содержит их.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rapidfuzz import fuzz  # noqa: E402

from tools import claims, ingest, lock, tables  # noqa: E402
from tools.common import die, project_path, setup_stdio, sha256_file  # noqa: E402
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
            if before and count_negations(before[-1].strip(",.;:()\"'")):
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


def run(slug, only=None) -> list[Finding]:
    """only — набор номеров проверок (1, 2, 3, 4, 11); None — все реализованные."""
    want = set(only) if only else {1, 2, 3, 4, 11}
    sources = ingest._load_sources(slug)
    out: list[Finding] = []
    if want & {1, 2, 3}:
        for c in claims.active(slug):
            out += _claim_findings(slug, c, sources, want)
    if 4 in want:
        out += check_refs(slug)
    if 11 in want:
        out += check_secrets(project_path(slug))
        out += check_lock()
    return out


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # ошибка использования — код 3, чтобы не путать с FAIL (1) и WARN (2)
        self.print_usage(sys.stderr)
        print(f"Ошибка: {message}. Что сделать: `python tools/check.py --help`.", file=sys.stderr)
        sys.exit(3)


def main(argv=None) -> int:
    setup_stdio()
    ap = _Parser(description="Проверка реестра утверждений: цитаты, числа с единицами, ячейки таблиц, ссылки, ключи.",
                 epilog="Коды выхода: 0 — всё прошло, 1 — есть FAIL, 2 — есть WARN, 3 — ошибка использования.")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    ap.add_argument("--only", help="номера проверок через запятую, например 1,2,3,4,11")
    ap.add_argument("--repo", action="store_true", help="для проверки 11 просканировать и всю папку агента, а не только проект")
    a = ap.parse_args(argv)
    try:
        only = {int(x) for x in a.only.split(",") if x.strip()} if a.only else None
    except ValueError:
        die("--only: нужны номера проверок через запятую. Что сделать: например `--only 1,2,3,4,11`.", code=3)
    if only and not only <= {1, 2, 3, 4, 11}:
        die("--only: сейчас реализованы проверки 1, 2, 3, 4 и 11. Что сделать: укажи номера из этого списка.", code=3)
    findings = run(a.project, only)
    if a.repo and (only is None or 11 in only):
        findings += check_secrets(Path(__file__).resolve().parent.parent)
    for f in findings:
        if f.level != "OK":
            print(f"[{f.level}] п.{f.check} {f.target}: {f.msg}" + (f" {f.hint}" if f.hint else ""))
    n = {lv: sum(1 for f in findings if f.level == lv) for lv in ("OK", "WARN", "FAIL")}
    print(f"Итого: OK {n['OK']}, WARN {n['WARN']}, FAIL {n['FAIL']}.")
    return 1 if n["FAIL"] else 2 if n["WARN"] else 0


if __name__ == "__main__":
    sys.exit(main())
