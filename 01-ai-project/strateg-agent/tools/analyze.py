# analyze.py: детерминированный анализ таблиц: cell (ячейка → fact без LLM), profile (единицы, периоды, пропуски, N, дубликаты, выбросы), calc (воспроизводимый расчёт calc/<C-id>.py); без него числа из таблиц и оценки пришлось бы доверять модели.
from __future__ import annotations

import argparse
import os
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from tools import claims, ingest, numparse, tables  # noqa: E402
from tools.common import die, project_path, setup_stdio, sha256_file, write_text_atomic  # noqa: E402

WRITER = "analyze.py"
CALC_TIMEOUT = 60  # секунд на один расчёт
RESULT_RE = re.compile(r"^RESULT=\s*([-+−]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?)\s*(.*)$")
YEAR_KEYS = ("год", "year")
QUARTER_KEYS = ("квартал", "quarter")
UNIT_HINT = re.compile(r"(?<![а-яёa-z])(тыс\.?|млн|млрд|руб\w*|чел\w*|поезд\w*|шт\.?|единиц\w*|гб|мб)(?![а-яёa-z])|(%|₽|\$|€)", re.IGNORECASE)
MAX_LIST = 10  # строк в каждом списке профиля


def add_cell_claim(slug, sid: str, locator: str, questions: list[str] | None = None) -> tuple[str, tables.Cell]:
    src = next((s for s in ingest._load_sources(slug) if s["id"] == sid), None)
    if src is None:
        raise ValueError(f"источника {sid} нет в проекте. Что сделать: `python tools/ingest.py <файл.xlsx> --found-by user`.")
    if src["kind"] != "table":
        raise ValueError(f"{sid} — {src['kind']}, а не таблица. Что сделать: для текста факты берёт extract.py.")
    path = project_path(slug) / "materials" / f"{sid}.{src['ext']}"
    if not path.is_file() or sha256_file(path) != src["sha256"]:
        raise ValueError(f"оригинал {sid} отсутствует или изменён. Что сделать: добавь таблицу заново через ingest.py.")
    cell = tables.get_cell(path, locator)
    rec = {
        # шапка не распознана → не fact, а estimate (docs/07): человек должен подтвердить толкование
        "type": "fact" if cell.header_ok else "estimate",
        "text": tables.render(cell),
        "source": sid,
        "locator": cell.locator,
        "quote": tables.render(cell),
        "dims": dict(cell.dims),
        "extracted_by": WRITER,
        "question": list(questions or []),
    }
    if not isinstance(cell.value, str):
        rec["value"] = cell.value
    return claims.add(slug, rec), cell


# ---------- профиль данных ----------

def _table_source(slug, sid: str) -> Path:
    src = next((x for x in ingest._load_sources(slug) if x["id"] == sid), None)
    if src is None:
        raise ValueError(f"источника {sid} нет в проекте. Что сделать: `python tools/ingest.py <файл.xlsx> --found-by user`.")
    if src["kind"] != "table":
        raise ValueError(f"{sid} — {src['kind']}, а не таблица. Что сделать: профиль строится только для xlsx/csv.")
    path = project_path(slug) / "materials" / f"{sid}.{src['ext']}"
    if not path.is_file():
        raise ValueError(f"оригинал {sid} отсутствует. Что сделать: добавь таблицу заново через ingest.py.")
    return path


def _dim(dims: dict, keys) -> str | None:
    for k, v in dims.items():
        if str(k).strip().lower() in keys:
            return str(v).strip()
    return None


def _period(dims: dict):
    y, q = _dim(dims, YEAR_KEYS), _dim(dims, QUARTER_KEYS)
    try:
        yi = int(float(y)) if y is not None else None
        qi = int(float(q)) if q is not None else None
    except ValueError:
        return None
    return (yi, qi) if yi is not None else None


def _quarters_between(lo, hi) -> list[tuple[int, int]]:
    out, (y, q) = [], lo
    while (y, q) <= hi:
        out.append((y, q))
        y, q = (y, q + 1) if q < 4 else (y + 1, 1)
    return out


def _fmt(v) -> str:
    return tables.fmt_value(v) if not isinstance(v, str) else v


def _series_key(dims: dict) -> tuple:
    return tuple((str(k), str(v)) for k, v in dims.items() if str(k).strip().lower() not in YEAR_KEYS + QUARTER_KEYS)


def _series_name(key: tuple) -> str:
    return "; ".join(f"{k}={v}" for k, v in key) or "(одна серия)"


def _pname(per) -> str:
    if per is None:
        return "?"
    return f"{per[0]}-Q{per[1]}" if per[1] else str(per[0])


def build_profile(path: Path, sid: str) -> str:
    cells, notes = tables.parse_table(path)
    nums = [c for c in cells if not isinstance(c.value, str)]
    sheets = sorted({c.sheet for c in cells})
    lines = [f"# Профиль данных {sid}", "", f"Файл: {Path(path).name}. Строится детерминированно (analyze.py profile), без LLM.", "",
             "## Размер (N)", f"- ячеек данных: {len(cells)}, из них числовых: {len(nums)}",
             f"- листов с данными: {len(sheets)}" + (f" ({', '.join(sheets)})" if sheets else ""),
             f"- примечаний под таблицей: {len(notes)}"]
    flags: list[str] = []
    if not nums:
        flags.append("числовых ячеек нет: профиль пуст. Что сделать: проверь, что файл содержит данные, а не только текст.")
    bad = [c for c in cells if not c.header_ok]
    if bad:
        flags.append(f"шапка не распознана у {len(bad)} ячеек (например {bad[0].locator}): толкование нужно подтвердить вручную.")
    # единицы
    hints: dict[str, int] = defaultdict(int)
    texts = [t for _, t in notes] + [str(v) for c in cells[:2000] for v in list(c.dims.keys()) + list(c.dims.values())]
    for text in texts:
        for m in UNIT_HINT.finditer(text):
            hints[m.group(0).lower()] += 1
    lines += ["", "## Единицы"]
    if hints:
        lines.append("- упоминания в шапках и примечаниях: " + ", ".join(f"«{k}» x{v}" for k, v in sorted(hints.items(), key=lambda x: -x[1])[:MAX_LIST]))
    else:
        lines.append("- единицы в шапках и примечаниях не найдены")
        flags.append("единицы измерения не указаны в шапке или примечаниях: не складывай числа, пока единица неизвестна.")
    for sh, t in notes[:MAX_LIST]:
        lines.append(f"- примечание ({sh}): {t[:200]}")
    # периоды
    periods: dict[tuple, set] = defaultdict(set)
    series_all: dict[tuple, dict] = defaultdict(dict)
    for c in nums:
        per = _period(c.dims)
        key = (c.sheet,) + _series_key(c.dims)
        series_all[key][per] = c.value
        if per is not None:
            periods[key].add(per)
    lines += ["", "## Периоды и пропуски"]
    allp = sorted({p for ps in periods.values() for p in ps})
    if not allp:
        lines.append("- периоды (измерения «Год»/«Квартал») не найдены")
    else:
        quarterly = all(q is not None for _, q in allp)
        lines.append(f"- период данных: {_pname(allp[0])} ... {_pname(allp[-1])}; серий: {len(periods)}")
        if quarterly:
            have = set(allp)
            miss = [p for p in _quarters_between(allp[0], allp[-1]) if p not in have]
            if miss:
                txt = ", ".join(_pname(p) for p in miss[:MAX_LIST])
                lines.append(f"- ПРОПУЩЕННЫЙ КВАРТАЛ во всей таблице: {txt}")
                flags.append(f"пропущены кварталы во всей таблице: {txt}.")
            gaps = []
            for key, ps in periods.items():
                m = [p for p in _quarters_between(min(ps), max(ps)) if p not in ps]
                if m:
                    gaps.append((key, m))
            if gaps:
                lines.append(f"- серий с пропуском квартала внутри ряда: {len(gaps)}")
                for key, m in gaps[:MAX_LIST]:
                    lines.append(f"  - {_series_name(key[1:])}: нет {', '.join(_pname(p) for p in m[:6])}")
                flags.append(f"в {len(gaps)} сериях пропущен квартал внутри ряда (пример: {_series_name(gaps[0][0][1:])}).")
            if not miss and not gaps:
                lines.append("- пропусков кварталов нет")
            tail = [k for k, ps in periods.items() if max(ps) < allp[-1]]
            if tail:
                lines.append(f"- серий, оборванных раньше последнего периода {_pname(allp[-1])}: {len(tail)}")
        else:
            years = sorted({y for y, _ in allp})
            miss_y = [y for y in range(years[0], years[-1] + 1) if y not in years]
            lines.append("- пропущенные годы: " + (", ".join(map(str, miss_y)) if miss_y else "нет"))
            if miss_y:
                flags.append(f"пропущены годы: {', '.join(map(str, miss_y))}.")
    # дубликаты
    seen: dict[tuple, int] = defaultdict(int)
    for c in cells:
        seen[(c.sheet, tuple(sorted((str(k), str(v)) for k, v in c.dims.items())))] += 1
    dup = {k: n for k, n in seen.items() if n > 1}
    lines += ["", "## Дубликаты"]
    if dup:
        lines.append(f"- повторяющихся комбинаций измерений: {len(dup)}")
        for (sh, d), n in list(dup.items())[:MAX_LIST]:
            lines.append(f"  - {sh}: {'; '.join(f'{k}={v}' for k, v in d)} x{n}")
        flags.append(f"{len(dup)} комбинаций измерений встречаются несколько раз: суммирование удвоит значения.")
    else:
        lines.append("- дубликатов (одинаковых комбинаций измерений) нет")
    # выбросы
    lines += ["", "## Выбросы"]
    neg = [c for c in nums if c.value < 0]
    if neg:
        lines.append(f"- отрицательных значений: {len(neg)} (например {neg[0].locator} = {_fmt(neg[0].value)})")
        flags.append(f"{len(neg)} отрицательных значений: проверь, допустимы ли они для этого показателя.")
    outl = []
    for key, ser in series_all.items():
        vals = list(ser.values())
        if len(vals) < 8:
            continue
        qs = statistics.quantiles(vals, n=4)
        iqr = qs[2] - qs[0]
        if iqr <= 0:
            continue
        lo, hi = qs[0] - 3 * iqr, qs[2] + 3 * iqr
        outl += [(key, per, v) for per, v in ser.items() if v < lo or v > hi]
    if outl:
        lines.append(f"- значений дальше 3xIQR от квартилей своей серии: {len(outl)}")
        for key, per, v in outl[:MAX_LIST]:
            lines.append(f"  - {_series_name(key[1:])} {_pname(per)}: {_fmt(v)}")
        flags.append(f"{len(outl)} выбросов (3xIQR внутри серии): проверь, не ошибка ли это в данных.")
    elif not neg:
        lines.append("- выбросов не найдено (серии короче 8 точек не оцениваются)")
    lines += ["", "## Что проверить до расчётов"]
    lines += [f"- {f}" for f in flags] or ["- замечаний нет"]
    return "\n".join(lines) + "\n"


def profile(slug, sid: str) -> Path:
    """Пишет calc/profile-<sid>.md: единицы, периоды и пропуски, N, дубликаты, выбросы."""
    path = _table_source(slug, sid)
    out = project_path(slug) / "calc" / f"profile-{sid}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(out, build_profile(path, sid))
    return out


# ---------- воспроизводимые расчёты ----------

def run_calc_ex(slug, cid: str, timeout: float = CALC_TIMEOUT) -> tuple[float, str, numparse.Num]:
    """Запускает calc/<cid>.py отдельным процессом: (число как напечатано, единица, Num с учётом «млн»/«тыс»)."""
    root = project_path(slug)
    script = root / "calc" / f"{cid}.py"
    if not script.is_file():
        raise ValueError(f"расчёта calc/{cid}.py нет. Что сделать: положи скрипт в calc/{cid}.py (последняя строка вывода `RESULT=<число> <единица>`).")
    try:
        r = subprocess.run([sys.executable, str(script)], cwd=str(root), capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        raise ValueError(f"расчёт calc/{cid}.py не уложился в {timeout:g} с. Что сделать: упрости расчёт или убери из него долгие циклы.") from None
    out = r.stdout.decode("utf-8", errors="replace")
    if r.returncode != 0:
        tail = " | ".join(r.stderr.decode("utf-8", errors="replace").strip().splitlines()[-2:]) or "без сообщения"
        raise ValueError(f"расчёт calc/{cid}.py завершился с ошибкой (код {r.returncode}): {tail}. Что сделать: запусти скрипт вручную и исправь ошибку.")
    last = next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()), "")
    m = RESULT_RE.match(last)
    if not m:
        raise ValueError(f"последняя строка вывода calc/{cid}.py не вида `RESULT=<число> <единица>` (получено: «{last[:80]}»). "
                         "Что сделать: допиши в конец скрипта print(f\"RESULT={x} <единица>\").")
    raw, unit_txt = m.group(1).replace("−", "-").replace(",", "."), m.group(2).strip()
    value = float(raw)
    mult, unit = 1.0, None
    if unit_txt:
        probe = numparse.parse_numbers("1 " + unit_txt)
        if probe:
            mult, unit = probe[0].value, probe[0].unit
    dec = len(re.split(r"[eE]", raw.split(".")[1])[0]) if "." in raw else 0
    return value, unit_txt, numparse.Num(value * mult, unit, f"{raw} {unit_txt}".strip(), 0.5 * 10 ** -dec * mult)


def run_calc(slug, cid: str) -> float:
    """Число из последней строки `RESULT=<число> <единица>` скрипта calc/<cid>.py."""
    return run_calc_ex(slug, cid)[0]


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(description="Детерминированный анализ таблиц проекта: ячейка как fact, профиль данных, воспроизводимый расчёт.",
                                 epilog="Расчёты лежат в calc/<C-id>.py; последняя строка вывода — `RESULT=<число> <единица>`. "
                                        "check.py (проверка 3) запускает их для утверждений типа estimate.")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("cell", help="записать значение ячейки таблицы как fact (extracted_by: analyze.py)")
    s.add_argument("source", help="id источника, например S-005")
    s.add_argument("locator", help='ячейка вида "Лист!C14"')
    s.add_argument("--question", action="append", help="вопрос, к которому относится факт (например Q1); можно несколько раз")
    s = sub.add_parser("profile", help="профиль таблицы: единицы, периоды и пропуски, N, дубликаты, выбросы (пишет calc/profile-<S-id>.md)")
    s.add_argument("source", help="id источника-таблицы, например S-005")
    s = sub.add_parser("calc", help="запустить calc/<C-id>.py и показать результат (последняя строка вывода `RESULT=<число> <единица>`)")
    s.add_argument("claim", help="id утверждения, например C-021")
    a = ap.parse_args(argv)
    if a.cmd == "profile":
        try:
            out = profile(a.project, a.source)
        except ValueError as e:
            die(str(e))
        print(f"Профиль записан: {out}")
        return 0
    if a.cmd == "calc":
        try:
            v, unit, _ = run_calc_ex(a.project, a.claim)
        except ValueError as e:
            die(str(e))
        print(f"{a.claim}: RESULT={v:g} {unit}".rstrip())
        return 0
    try:
        cid, cell = add_cell_claim(a.project, a.source, a.locator, a.question)
    except ValueError as e:
        die(str(e))
    print(f"{cid}: {tables.render(cell)}")
    if not cell.header_ok:
        print(f"ВНИМАНИЕ: шапка ячейки не распознана ({tables.UNKNOWN_MARK}), записан estimate, а не fact. "
              f"Что сделать: проверить шапку в Excel и исправить файл либо подтвердить толкование расчётом calc/{cid}.py, "
              "иначе check.py даст FAIL по этому утверждению.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
