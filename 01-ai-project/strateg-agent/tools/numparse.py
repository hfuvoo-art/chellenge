# Разбор чисел с единицами и нормализация цитат (У9): без него «+3 п.п.» совпадёт с «3 %», а «7 $ за 15 ГБ» с «15 $ за 3 ГБ».
from __future__ import annotations

import re
from dataclasses import dataclass

YEAR_MIN, YEAR_MAX = 1990, 2035
EPS = 1e-9


@dataclass
class Num:
    value: float
    unit: str | None
    raw: str
    precision: float  # половина последнего записанного разряда (с учётом тыс./млн)


MULT = {"тыс": 1e3, "тысяч": 1e3, "тысячи": 1e3, "млн": 1e6, "миллион": 1e6, "миллиона": 1e6, "миллионов": 1e6,
        "млрд": 1e9, "миллиард": 1e9, "миллиарда": 1e9, "миллиардов": 1e9}
UNITS = {
    "%": "%", "процент": "%", "процента": "%", "процентов": "%",
    "п.п.": "п.п.", "пп": "п.п.", "пункт": "п.п.", "пункта": "п.п.", "пунктов": "п.п.",
    "₽": "₽", "руб": "₽", "рубль": "₽", "рубля": "₽", "рублей": "₽", "р": "₽",
    "$": "$", "долл": "$", "доллар": "$", "доллара": "$", "долларов": "$", "usd": "$",
    "€": "€", "евро": "€", "eur": "€",
    "гб": "ГБ", "gb": "ГБ", "гигабайт": "ГБ", "гигабайта": "ГБ",
    "мб": "МБ", "mb": "МБ", "мегабайт": "МБ", "мегабайта": "МБ",
    "мин": "мин", "минут": "мин", "минута": "мин", "минуты": "мин",
    "день": "день", "дня": "день", "дней": "день", "сутки": "день", "суток": "день",
    "мес": "мес", "месяц": "мес", "месяца": "мес", "месяцев": "мес",
    "год": "год", "года": "год", "году": "год", "лет": "год", "г": "год", "гг": "год",
    "чел": "чел", "человек": "чел", "человека": "чел",
    "шт": "шт", "штук": "шт", "штуки": "шт", "штука": "шт",
    "раз": "раз", "раза": "раз",
    "кв": "кв", "квартал": "кв", "квартала": "кв", "кварталов": "кв",
}
_NUM = r"\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_SEP = r"(?:\s*[–—]\s*|-|\s+до\s+)"
NUM_RE = re.compile(
    rf"(?<![A-Za-zА-Яа-яЁё\d_])(?P<sign>[−\-]?)(?P<n1>{_NUM})(?:{_SEP}(?P<n2>{_NUM}))?(?![\d])")
TOKEN_RE = re.compile(r"\s*(п\.\s?п\.|[A-Za-zА-Яа-яЁё]+\.?|[%$€₽])")
ROMAN_Q = re.compile(r"(?<![A-Za-zА-Яа-яЁё\d])(IV|III|II|I|[1-4])\s*(?:[-–]?\s*й\s*)?кв(?:артал\w*|\.)?", re.IGNORECASE)
EN_Q = re.compile(r"(?<![A-Za-z\d])Q([1-4])(?![\d])", re.IGNORECASE)
DATE_DMY = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.((?:19|20)\d{2})\b")
DATE_ISO = re.compile(r"\b((?:19|20)\d{2})-\d{2}-\d{2}\b")
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
NEG_RE = re.compile(r"(?<![\wё])(?:не|нет|без|ни|not|no)(?![\wё])|n't")
_TRANS = str.maketrans({"«": '"', "»": '"', "„": '"', "“": '"', "”": '"', "‟": '"', "‘": "'", "’": "'",
                        "−": "-", "–": "-", "—": "-", "­": None, "ё": "е", "Ё": "е"})


def normalize_quote(s: str) -> str:
    s = (s or "").replace("\r", "")
    s = re.sub(r"(\w)[-­]\s*\n\s*(\w)", r"\1\2", s)  # перенос слова из PDF: «мар-\nкетинг»
    s = s.lower().translate(_TRANS)
    return re.sub(r"\s+", " ", s).strip()


def count_negations(s: str) -> int:
    return len(NEG_RE.findall(s))


def _to_float(raw: str) -> tuple[float, int]:
    t = re.sub(r"[   ]", "", raw).replace(",", ".")
    dec = len(t.split(".")[1]) if "." in t else 0
    return float(t), dec


def _unit_after(text: str, end: int) -> tuple[float, str | None, int]:
    """(множитель, единица, позиция конца множителя); конец множителя нужен, чтобы raw включал «тыс.»."""
    mult, pos, unit, mend = 1.0, end, None, end
    for _ in range(2):
        m = TOKEN_RE.match(text, pos)
        if not m:
            break
        tok = re.sub(r"\s+", "", m.group(1)).lower()
        pos = m.end()
        key = tok.rstrip(".") if tok != "п.п." else tok
        if key in MULT and mult == 1.0:
            mult, mend = MULT[key], pos
            continue
        if key in UNITS:
            unit = UNITS[key]
        break
    return mult, unit, mend


def _mask(text: str, m: re.Match, keep: str = "") -> str:
    return text[:m.start()] + keep.ljust(m.end() - m.start()) + text[m.end():]


def parse_numbers(text: str) -> list[Num]:
    """Числа текста вместе с единицей: ближайший токен справа (≤2 токенов); тыс/млн/млрд → множитель."""
    out: list[tuple[int, Num]] = []
    t = text or ""
    for m in list(DATE_DMY.finditer(t)):  # даты → только год
        t = _mask(t, m, " " * (m.end() - m.start() - 4) + m.group(3))
    for m in list(DATE_ISO.finditer(t)):
        t = _mask(t, m, m.group(1))
    for rx in (ROMAN_Q, EN_Q):  # кварталы забираем отдельно и вырезаем, чтобы не считать дважды
        for m in list(rx.finditer(t)):
            q = m.group(1).upper()
            out.append((m.start(), Num(float(ROMAN.get(q) or int(q)), "кв", m.group(0), 0.5)))
            t = _mask(t, m)
    for m in NUM_RE.finditer(t):
        sign = -1.0 if m.group("sign") else 1.0
        if m.group("sign") == "-" and m.start() > 0 and t[m.start() - 1].isdigit():
            sign = 1.0
        mult, unit, mend = _unit_after(t, m.end())
        if unit is None and m.start() > 0 and t[m.start() - 1] in "$€":  # «$7»
            unit = t[m.start() - 1]
        for g, s in (("n1", sign), ("n2", 1.0)):
            raw = m.group(g)
            if raw is None:
                continue
            v, dec = _to_float(raw)
            if mult != 1.0:
                raw = raw + t[m.end():mend]  # «1,5» + « тыс.»
            u = unit
            if mult == 1.0 and u in (None, "год") and float(v).is_integer() and YEAR_MIN <= v <= YEAR_MAX:
                u = "год"
            out.append((m.start(g), Num(s * v * mult, u, raw, 0.5 * 10 ** -dec * mult)))
    out.sort(key=lambda x: x[0])
    return [n for _, n in out]


def is_year(n: Num) -> bool:
    return n.unit == "год" and YEAR_MIN <= n.value <= YEAR_MAX and n.precision <= 0.5


def _close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol + EPS


def num_match(f: Num, quote_nums) -> bool:
    """|f − q| ≤ f.precision и единицы равны; x% совпадает с безразмерным x или x/100."""
    for q in quote_nums:
        if f.unit == q.unit:
            if _close(f.value, q.value, f.precision):
                return True
        elif f.unit == "%" and q.unit is None:
            if _close(f.value, q.value, f.precision) or _close(f.value / 100, q.value, f.precision / 100):
                return True
        elif f.unit is None and q.unit == "%":
            if _close(f.value, q.value, f.precision) or _close(f.value, q.value / 100, f.precision):
                return True
    return False
