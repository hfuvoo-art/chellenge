# Отзывы Google Play и очистка ПДн в CSV: без него в материалы попадают авторы, телефоны и почты, а окна сравнения не считаются.
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date, datetime

HEADER = ["date", "rating", "version", "text"]
PAGE = 200
def _norm(h: str) -> str:
    return re.sub(r"[\s_-]+", "", h.strip().lower())


# только точные заголовки: подстрочное совпадение ломало бы обычные таблицы («Имя тарифа», «Количество пользователей»)
_PII_EXACT = {_norm(x) for x in (
    "author", "автор", "имя автора", "автор отзыва", "reviewer", "user", "username", "userid", "user_name", "user name",
    "phone", "телефон", "email", "e-mail", "почта", "mail", "reviewid", "review id", "id отзыва", "фио", "контакт")}
_NAME_COLS = {"name", "имя"}  # только если CSV распознан как отзывы
_REVIEW_HINTS = {"text", "отзыв", "content", "comment"}
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_RE = re.compile(
    r"\+\d[\d\s().-]{8,}\d"
    r"|(?<![\d-])[78][\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)"
    r"|(?<!\d)\(\d{3}\)[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)"
    r"|(?<![\d-])\d{3}-\d{3}-\d{2}-\d{2}(?!\d)")


@dataclass(frozen=True)
class Review:
    date: str
    rating: int | None
    version: str
    text: str


def _gplay_reviews(app_id, **kw):
    """Тонкая обёртка над google_play_scraper.reviews (в тестах подменяется)."""
    from google_play_scraper import Sort, reviews
    return reviews(app_id, sort=Sort.NEWEST, **kw)


def _day(v) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)[:10]


def _clean_text(t) -> str:
    return re.sub(r"\s+", " ", str(t or "")).strip()


def review_hash(r: Review) -> str:
    return hashlib.sha256((r.text + r.date).encode("utf-8")).hexdigest()


def fetch_gplay(app_id: str, since, until=None, max_n: int = 2000) -> list[Review]:
    """Свежие → старые страницами по 200 до даты since; авторы и ID не берутся, дубли по sha256(text+date) убираются."""
    since_s, until_s = _day(since), (_day(until) if until else None)
    out: list[Review] = []
    seen: set[str] = set()
    fetched = 0
    token = None
    while fetched < max_n:
        kw = dict(lang="ru", country="ru", count=min(PAGE, max_n - fetched))
        if token is not None:
            kw["continuation_token"] = token
        batch, token = _gplay_reviews(app_id, **kw)
        if not batch:
            break
        reached = False
        for raw in batch:
            if fetched >= max_n:
                break
            fetched += 1
            d = _day(raw.get("at"))
            if d < since_s:
                reached = True
                continue
            if until_s and d > until_s:
                continue
            score = raw.get("score")
            r = Review(d, int(score) if score is not None else None, str(raw.get("reviewCreatedVersion") or ""),
                       _clean_text(raw.get("content")))
            h = review_hash(r)
            if h not in seen:
                seen.add(h)
                out.append(r)
        if reached or token is None:
            break
    return out


# ---------- CSV ----------

def reviews_to_rows(rs: list[Review]) -> list[list[str]]:
    return [list(HEADER)] + [[r.date, "" if r.rating is None else str(r.rating), r.version, r.text] for r in rs]


def rows_to_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue().encode("utf-8")


def write_reviews_csv(rs: list[Review], path) -> None:
    from pathlib import Path
    Path(path).write_bytes(rows_to_bytes(reviews_to_rows(rs)))


def parse_csv_bytes(raw: bytes) -> list[list[str]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    head = text.split("\n", 1)[0]
    delim = max(";\t,", key=head.count) if any(d in head for d in ";\t,") else ","
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))


def _looks_like_reviews(headers: list[str]) -> bool:
    n = [_norm(h) for h in headers]
    return [h.strip() for h in headers] == HEADER or any(x in _REVIEW_HINTS for x in n)


def is_pii_header(h: str, reviewish: bool = False) -> bool:
    n = _norm(h)
    return n in _PII_EXACT or (reviewish and n in _NAME_COLS)


def mask_pii(text: str) -> tuple[str, int]:
    n = 0

    def sub(tag):
        def f(_m):
            nonlocal n
            n += 1
            return tag
        return f
    text = _EMAIL_RE.sub(sub("[email]"), text)
    text = _PHONE_RE.sub(sub("[телефон]"), text)
    return text, n


def clean_rows(rows: list[list[str]]) -> tuple[list[list[str]], int]:
    """Убирает колонки автора/имени/телефона/почты по заголовкам и маскирует телефоны и почты в ячейках. Возвращает (строки, N убранного ПДн)."""
    if not rows:
        return rows, 0
    reviewish = _looks_like_reviews(rows[0])
    drop = {i for i, h in enumerate(rows[0]) if is_pii_header(h, reviewish)}
    removed = sum(1 for r in rows[1:] for i in drop if i < len(r) and r[i].strip())
    out = []
    for ri, r in enumerate(rows):
        new = []
        for i, c in enumerate(r):
            if i in drop:
                continue
            if ri > 0:
                c, k = mask_pii(c)
                removed += k
            new.append(c)
        out.append(new)
    return out, removed


def is_reviews_header(rows: list[list[str]]) -> bool:
    return bool(rows) and [h.strip() for h in rows[0]] == HEADER


def reviews_from_rows(rows: list[list[str]]) -> list[Review]:
    out = []
    for r in rows[1:]:
        r = (r + [""] * 4)[:4]
        try:
            rating = int(float(r[1]))
        except ValueError:
            rating = None
        out.append(Review(r[0].strip()[:10], rating, r[2].strip(), _clean_text(r[3])))
    return out


# ---------- md ----------

def window_counts(rs: list[Review]) -> dict[str, tuple[int, float | None]]:
    acc: dict[str, list[Review]] = {}
    for r in rs:
        acc.setdefault(r.date[:7], []).append(r)
    res = {}
    for k in sorted(acc):
        rt = [r.rating for r in acc[k] if r.rating is not None]
        res[k] = (len(acc[k]), sum(rt) / len(rt) if rt else None)
    return res


def _plural(n: int) -> str:
    if n % 100 in range(11, 15):
        return "отзывов"
    return {1: "отзыв", 2: "отзыва", 3: "отзыва", 4: "отзыва"}.get(n % 10, "отзывов")


def render_md(rs: list[Review]) -> tuple[str, int]:
    """¶1 — окна-месяцы (число отзывов, средняя оценка); ¶2… — отзывы по одному абзацу: дата · оценка · версия · текст."""
    lines = []
    for k, (n, avg) in window_counts(rs).items():
        a = "нет оценок" if avg is None else f"средняя оценка {avg:.2f}".replace(".", ",")
        lines.append(f"{k}: {n} {_plural(n)}, {a}")
    paras = ["Окна по месяцам. " + "; ".join(lines) if lines else "Отзывов нет."]
    for r in rs:
        v = f" · v{r.version}" if r.version else ""
        paras.append(f"{r.date} · оценка {'?' if r.rating is None else r.rating}{v} · {r.text}")
    paras = [p.replace("<!--", "<! --") for p in paras]
    md = "\n\n".join(f"<!-- ¶{i} -->\n{p}" for i, p in enumerate(paras, 1))
    return md, sum(len(p) for p in paras)
