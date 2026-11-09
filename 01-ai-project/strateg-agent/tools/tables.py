# Разбор таблиц (xlsx/csv) в ячейки с измерениями: шапка, объединённые ячейки, кварталы, примечания; без него табличные факты берутся «на глаз» и ссылаются на не ту строку.
from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CSV_SHEET = "csv"  # имя «листа» для csv: не зависит от имени файла, чтобы локаторы не ломались при копировании в проект
UNKNOWN_MARK = "[заголовок?]"
NOTE_RE = re.compile(r"^\s*(примечани|источник|прим\.|сноска|\*)", re.IGNORECASE)
YEAR_RE = re.compile(r"^\s*((?:19|20)\d{2})\s*(?:г\.?|год\w*)?\s*$", re.IGNORECASE)
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
QUARTER_RE = re.compile(r"^\s*(?:(IV|III|II|I|[1-4])\s*[-–]?\s*(?:й\s*)?(?:кв(?:артал)?\.?)|q\s*([1-4]))\s*$", re.IGNORECASE)
NUM_RE = re.compile(r"^[+\-−]?\d+(?:[.,]\d+)?$")


@dataclass
class Cell:
    sheet: str
    ref: str  # локальный адрес: C14
    dims: dict[str, str] = field(default_factory=dict)
    value: float | str = 0
    header_ok: bool = True

    @property
    def locator(self) -> str:
        return f"{self.sheet}!{self.ref}"


# ---------- числа и шапки ----------

def parse_number(text: str):
    """«1 302 417», «12,5», «−3» → число; иначе None."""
    s = text.replace(" ", "").replace(" ", "").replace(" ", "").replace("−", "-")
    if not NUM_RE.match(s):
        return None
    s = s.replace(",", ".")
    return float(s) if "." in s else int(s)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_year_int(v) -> bool:
    return _is_num(v) and float(v).is_integer() and 1900 <= v <= 2100


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v).split())  # переводы строк внутри ячейки не должны рвать строку материала


def _quarter(t: str) -> str | None:
    m = QUARTER_RE.match(t)
    if not m:
        return None
    q = (m.group(1) or m.group(2)).upper()
    return str(ROMAN.get(q) or int(q))


def _year(t: str) -> str | None:
    m = YEAR_RE.match(t)
    return m.group(1) if m else None


def _group(n: int) -> str:
    s = str(n)
    return " ".join([s[max(0, i - 3):i] for i in range(len(s), 0, -3)][::-1])


def fmt_value(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if isinstance(v, int):
        return sign + _group(v)
    ip, _, fp = f"{v:.10f}".rstrip("0").partition(".")
    return sign + _group(int(ip)) + ("," + fp if fp else "")


def render(cell: Cell) -> str:
    dims = "; ".join(f"{k}={v}" for k, v in cell.dims.items())
    mark = f" {UNKNOWN_MARK}" if not cell.header_ok else ""
    return f"{cell.sheet}!{cell.ref} [{dims}]{mark} = {fmt_value(cell.value)}"


# ---------- разбор листа ----------

def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _parse_grid(sheet: str, grid: dict, ghosts: set, nrows: int, ncols: int,
                strings_numeric: bool) -> tuple[list[Cell], list[tuple[str, str]]]:
    """grid[(строка, столбец)] с 1; ghosts — продолжения объединённых ячеек (не данные)."""

    def val(r, c):
        v = grid.get((r, c))
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
            if strings_numeric:
                n = parse_number(v)
                if n is not None:
                    return n
        return v

    def row_vals(r):
        return [(c, val(r, c)) for c in range(1, ncols + 1) if val(r, c) is not None]

    def is_data_row(r, strict=True):
        vs = row_vals(r)
        if not vs or NOTE_RE.match(_text(vs[0][1])):
            return False
        nums = [v for _, v in vs if _is_num(v)]
        if not nums or (strict and len(nums) * 2 < len(vs)):  # старт таблицы: ≥50 % числовых; дальше достаточно одной (н/д в строке)
            return False
        return not (len(nums) >= 2 and all(_is_year_int(v) for v in nums))  # строка лет — шапка

    notes: list[tuple[str, str]] = []

    def add_note(r):
        vs = [(c, v) for c, v in row_vals(r) if (r, c) not in ghosts]  # продолжения объединённых ячеек не повторяем
        if vs:
            notes.append((f"{sheet}!{_col_letter(vs[0][0])}{r}", " | ".join(_text(v) for _, v in vs)))

    first = next((r for r in range(1, nrows + 1) if is_data_row(r)), None)
    if first is None:  # таблицы на листе нет: весь текст — примечания (паспорт, описание)
        for r in range(1, nrows + 1):
            add_note(r)
        return [], notes
    data_rows = [first]
    for r in range(first + 1, nrows + 1):
        if is_data_row(r, strict=False):
            data_rows.append(r)
        else:
            add_note(r)  # примечания и пустое под таблицей данными не считаются
    stat = {}
    for c in range(1, ncols + 1):
        nums = sum(1 for r in data_rows if _is_num(val(r, c)) and (r, c) not in ghosts)
        txts = sum(1 for r in data_rows if val(r, c) is not None and not _is_num(val(r, c)))
        stat[c] = (nums, txts)
    num_cols = [c for c in range(1, ncols + 1) if stat[c][0] >= 1 and stat[c][0] >= stat[c][1]]
    if not num_cols:
        return [], notes
    left = [c for c in range(1, ncols + 1) if c < num_cols[0] and stat[c][1] > stat[c][0]]
    levels = [r for r in range(1, first) if any(val(r, c) is not None for c in range(1, ncols + 1))]
    htext = {(r, c): _text(val(r, c)) for r in levels for c in range(1, ncols + 1)}
    for r in levels[:-1]:  # верхние уровни протягиваем вправо: сгруппированная шапка без слияния
        cur = ""
        for c in range(num_cols[0], ncols + 1):
            if htext[(r, c)]:
                cur = htext[(r, c)]
            elif c in num_cols and cur:
                htext[(r, c)] = cur
    kept = []
    for r in levels:
        texts = [htext[(r, c)] for c in num_cols]
        nonempty = [t for t in texts if t]
        if not nonempty:
            continue
        constant = (len(nonempty) == len(texts) and len(set(nonempty)) == 1  # заголовок таблицы, не измерение
                    and not (_year(nonempty[0]) or _quarter(nonempty[0])))  # но единственный год или квартал — измерение
        kept.append((r, constant, nonempty))
    use = [k for k in kept if not k[1]] or kept[-1:]
    kinds: dict[int, str] = {}
    for r, _, nonempty in use:
        def share(f, ne=nonempty):
            return sum(1 for t in ne if f(t)) * 2 >= len(ne)
        kinds[r] = "year" if share(_year) else "quarter" if share(_quarter) else "generic"
    names: dict[int, str] = {}
    used: set[str] = set()
    for r, _, _ne in use:
        base = {"year": "Год", "quarter": "Квартал", "generic": "Показатель"}[kinds[r]]
        name, i = base, 2
        while name in used:
            name, i = f"{base}{i}", i + 1
        used.add(name)
        names[r] = name
    title_rows = set()  # строка из одного повторяющегося текста (объединённый заголовок таблицы) имени столбца не даёт
    for r in levels:
        ts = [htext[(r, c)] for c in range(1, ncols + 1) if htext[(r, c)]]
        if len(ts) >= 2 and len(set(ts)) == 1:
            title_rows.add(r)
    left_names: dict[int, str] = {}
    for c in left:
        t = next((htext[(r, c)] for r in reversed(levels) if r not in title_rows and htext.get((r, c))), "")
        name = t or f"col{c}"
        while name in left_names.values() or name in used:
            name = f"{name}_{c}"
        left_names[c] = name
    cells: list[Cell] = []
    for r in data_rows:
        row_dims = {left_names[c]: _text(val(r, c)) for c in left if _text(val(r, c))}
        for c in num_cols:
            v = val(r, c)
            if v is None or (r, c) in ghosts:
                continue
            dims = dict(row_dims)
            ok = bool(use)
            for lr, _, _ne in use:
                t = htext[(lr, c)]
                if not t:
                    ok = False
                    continue
                k = kinds[lr]
                norm = _year(t) if k == "year" else _quarter(t) if k == "quarter" else t
                if norm is None:
                    ok = False
                    norm = t
                dims[names[lr]] = norm
            cells.append(Cell(sheet, f"{_col_letter(c)}{r}", dims, v if _is_num(v) else _text(v), ok))
    return cells, notes


# ---------- файлы ----------

def parse_workbook_ex(path) -> tuple[list[Cell], list[tuple[str, str]]]:
    import openpyxl
    wb = openpyxl.load_workbook(str(path), data_only=True)
    cells: list[Cell] = []
    notes: list[tuple[str, str]] = []
    for ws in wb.worksheets:
        grid = {}
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    grid[(c.row, c.column)] = c.value
        ghosts: set = set()
        for mr in ws.merged_cells.ranges:
            tl = ws.cell(mr.min_row, mr.min_col).value
            for r in range(mr.min_row, mr.max_row + 1):
                for c in range(mr.min_col, mr.max_col + 1):
                    if (r, c) != (mr.min_row, mr.min_col):
                        ghosts.add((r, c))
                        if tl is not None:
                            grid[(r, c)] = tl
        cs, ns = _parse_grid(ws.title, grid, ghosts, ws.max_row, ws.max_column, strings_numeric=False)
        cells += cs
        notes += ns
    return cells, notes


def _read_csv_rows(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    lines = text.splitlines()
    head = lines[0] if lines else ""
    delim = max(";\t,", key=head.count) if any(d in head for d in ";\t,") else ";"
    return list(csv.reader(lines, delimiter=delim))


def parse_csv_ex(path) -> tuple[list[Cell], list[tuple[str, str]]]:
    rows = _read_csv_rows(Path(path))
    grid = {(i, j): v for i, row in enumerate(rows, 1) for j, v in enumerate(row, 1) if v.strip()}
    ncols = max((len(r) for r in rows), default=0)
    return _parse_grid(CSV_SHEET, grid, set(), len(rows), ncols, strings_numeric=True)


def parse_table(path) -> tuple[list[Cell], list[tuple[str, str]]]:
    """(ячейки данных, примечания [(Лист!A5, текст)]) для xlsx/xlsm или csv."""
    if Path(path).suffix.lower() == ".csv":
        return parse_csv_ex(path)
    return parse_workbook_ex(path)


def parse_workbook(path) -> list[Cell]:
    return parse_workbook_ex(path)[0]


def parse_csv(path) -> list[Cell]:
    return parse_csv_ex(path)[0]


def get_cell(path, locator: str) -> Cell:
    """Ячейка по локатору «Лист!C14»; не ячейка данных (шапка, примечание, пусто) — ValueError."""
    sheet, sep, ref = str(locator).rpartition("!")
    ref = ref.replace("$", "").upper()
    if not sep or not re.match(r"^[A-Z]{1,3}\d+$", ref):
        raise ValueError(f"локатор «{locator}» не похож на ячейку. Что сделать: формат Лист!C14.")
    cells = parse_table(path)[0]
    for c in cells:
        if c.sheet == sheet and c.ref == ref:
            return c
    sheets = sorted({c.sheet for c in cells})
    raise ValueError(f"«{sheet}!{ref}» не ячейка данных (пустая, шапка или примечание, либо нет такого листа). "
                     f"Что сделать: проверь адрес в materials/<S-id>.md; листы с данными: {', '.join(sheets) or 'нет'}.")
