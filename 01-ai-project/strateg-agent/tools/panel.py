# panel.py: панель проекта одной статической HTML-страницей (где мы, что ждёт от человека, источники, стоимость); без неё руководитель вынужден читать чат и файлы, а бриф требует «пользователь видит продвижение».
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import webbrowser
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import extract, status  # noqa: E402
from tools.common import die, now_iso, project_path, read_text, read_yaml, setup_stdio, write_text_atomic  # noqa: E402

STEPS = [(1, "Постановка"), (2, "Сбор источников"), (3, "Исследование"), (4, "Варианты"), (5, "Стратегия"), (6, "После решения")]
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
OPT_RE = re.compile(r"^##\s+(O\d+)\s*·\s*([^·]+?)\s*·\s*(.+?)\s*$", re.M)
QSTATUS_RE = re.compile(r"^\s*[-*]\s*(Q\d+)\s*[—–-]+\s*\*\*(.+?)\*\*", re.M)
CSP = "default-src 'none'; style-src 'unsafe-inline'"
NONE = "пока нет"

CSS = """
:root{--bg:#f6f7f9;--fg:#1c2330;--mut:#5b6678;--card:#fff;--line:#d8dde6;--ok:#1d7a46;--cur:#1f4fbf;--red:#b3261e;--yel:#8a6100}
@media(prefers-color-scheme:dark){:root{--bg:#14171d;--fg:#e6e9ef;--mut:#9aa4b5;--card:#1d222b;--line:#323a47;--ok:#58c58b;--cur:#7aa2ff;--red:#ff8a80;--yel:#f0c050}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,Segoe UI,Arial,sans-serif;padding:16px}
main{max-width:860px;margin:0 auto}h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.1rem;margin:0 0 8px}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:12px 0}
.mut{color:var(--mut);font-size:.9rem}.red{color:var(--red);font-weight:600}.yel{color:var(--yel)}
.steps{display:flex;flex-wrap:wrap;gap:6px;padding:0;margin:0;list-style:none}
.steps li{flex:1 1 120px;border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-size:.9rem}
.steps .done{border-color:var(--ok);color:var(--ok)}.steps .cur{border-color:var(--cur);color:var(--cur);font-weight:700;border-width:2px}
.steps .next{color:var(--mut)}ul,ol{padding-left:20px;margin:4px 0}li{margin:3px 0}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top;font-size:.92rem}
.tag{display:inline-block;border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:.8rem;margin-left:4px}
.wait{border-left:4px solid var(--cur)}a{color:var(--cur);word-break:break-all}
@media(max-width:480px){body{padding:10px}td,th{font-size:.85rem}}
"""


def _c(s) -> str:
    return CTRL_RE.sub("", str(s if s is not None else ""))


def _e(s) -> str:
    return html.escape(_c(s), quote=True)


def _link(url: str) -> str:
    """Ссылка только http/https; всё остальное — просто текст."""
    u = _c(url).strip()
    try:
        ok = urlsplit(u).scheme.lower() in ("http", "https")
    except ValueError:
        ok = False
    return f'<a href="{_e(u)}" rel="noopener noreferrer">{_e(u)}</a>' if ok else _e(u)


def _sec(title: str, body: str, cls: str = "") -> str:
    return f'<section class="{cls}"><h2>{_e(title)}</h2>{body}</section>'


def _empty(text: str = NONE) -> str:
    return f'<p class="mut">{_e(text)}</p>'


def _err(msg: str) -> str:
    return f'<p class="red">{_e(msg)}</p>'


def _read(p: Path) -> str | None:
    try:
        return read_text(p) if p.is_file() else None
    except (OSError, UnicodeDecodeError):
        return None


def _section_md(text: str, title: str) -> str:
    m = re.search(rf"^##\s+{re.escape(title)}[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def _load_yaml(p: Path):
    """(данные, ошибка): отсутствие файла — (None, ''); битый файл — (None, текст)."""
    if not p.is_file():
        return None, ""
    try:
        return read_yaml(p), ""
    except Exception:  # noqa: BLE001 — битый yaml не должен ронять панель
        return None, f"{p.name} не читается (битый YAML). Что сделать: исправь файл."


def _title_block(d: Path, slug: str) -> str:
    brief = _read(d / "brief.md")
    q = _section_md(brief, "Вопрос") if brief else ""
    body = f'<p class="mut">Проект: {_e(slug)}</p>'
    body += f"<p>{_e(q)}</p>" if q else _empty("запроса пока нет (brief.md)")
    return f"<h1>{_e(slug)}</h1>{body}"


def _steps_block(st, err: str) -> str:
    if err:
        return _sec("Шаги", _err(err))
    step = st.get("step") if isinstance(st, dict) and isinstance(st.get("step"), dict) else {}
    n = step.get("n") if isinstance(step.get("n"), int) else 0
    items = []
    for i, name in STEPS:
        cls, mark = ("done", "сделан") if i < n else (("cur", "текущий") if i == n else ("next", "впереди"))
        items.append(f'<li class="{cls}">{i}. {_e(name)}<br><span class="mut">{mark}</span></li>')
    note = "" if n else _empty("работа ещё не начата")
    return _sec("Где мы", f'<ol class="steps">{"".join(items)}</ol>{note}')


def _waiting_block(st) -> str:
    point, question = status._waiting_parts(st.get("waiting") if isinstance(st, dict) else None)
    if point or question:
        txt = f"{point}: {question}" if point and question else (point or question)
        return _sec("Ждёт от вас", f"<p><b>{_e(txt)}</b></p>", "wait")
    return _sec("Ждёт от вас", "<p>ничего</p>")


def _human_block(st) -> str:
    rows = [h for h in ((st or {}).get("human") or []) if isinstance(h, dict)] if isinstance(st, dict) else []
    if not rows:
        return _sec("Решения в точках", _empty())
    lis = "".join(f"<li><b>{_e(h.get('point'))}</b>: {_e(h.get('summary'))} <span class=\"mut\">({_e(h.get('minutes'))} мин)</span></li>"
                  for h in rows)
    return _sec("Решения в точках", f"<ul>{lis}</ul>")


def _questions_block(d: Path) -> str:
    text = _read(d / "questions.md")
    qs = extract.parse_questions(text) if text else []
    if not qs:
        return _sec("Вопросы", _empty())
    stat = {}
    for code, s in QSTATUS_RE.findall(text):
        stat.setdefault(code, s.strip().rstrip("."))
    lis = []
    for code, q in qs:
        tag = f'<span class="tag">{_e(stat[code])}</span>' if code in stat else ""
        lis.append(f"<li><b>{_e(code)}</b> {_e(q)}{tag}</li>")
    return _sec("Вопросы", f"<ul>{''.join(lis)}</ul>")


def _sources_block(d: Path) -> str:
    data, err = _load_yaml(d / "sources.yaml")
    if err:
        return _sec("Источники", _err(err))
    srcs = [s for s in ((data or {}).get("sources") or []) if isinstance(s, dict)] if isinstance(data, dict) else []
    if not srcs:
        return _sec("Источники", _empty())
    rows = []
    for s in srcs:
        where = _link(s["url"]) if s.get("url") else _e(s.get("path") or s.get("ext") or "")
        tags = ""
        if s.get("warnings"):
            tags += f'<span class="tag yel">предупреждений: {len(s["warnings"]) if isinstance(s["warnings"], list) else 1}</span>'
        if s.get("suspicious"):
            tags += f'<span class="tag red">подозрительное: {len(s["suspicious"]) if isinstance(s["suspicious"], list) else 1}</span>'
        rows.append(f"<tr><td>{_e(s.get('id'))}</td><td>{_e(s.get('kind'))}</td><td>{_e(s.get('title'))}{tags}<br>{where}</td></tr>")
    return _sec("Источники", f"<table><tr><th>id</th><th>вид</th><th>название</th></tr>{''.join(rows)}</table>")


def _claims_block(d: Path) -> str:
    p = d / "claims.jsonl"
    if not p.is_file():
        return _sec("Утверждения", _empty())
    items, bad = [], 0
    for line in (_read(p) or "").splitlines():
        if not line.strip():
            continue
        try:
            o = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(o, dict):
            items.append(o)
        else:
            bad += 1
    warn = _err(f"claims.jsonl: нечитаемых строк {bad}. Что сделать: исправь файл.") if bad else ""
    if not items:
        return _sec("Утверждения", warn + _empty())
    by_type = Counter(_c(c.get("type") or "?") for c in items)
    by_status = Counter(_c(c.get("status") or "?") for c in items)
    t = ", ".join(f"{_e(k)}: {v}" for k, v in sorted(by_type.items()))
    s = ", ".join(f"{_e(k)}: {v}" for k, v in sorted(by_status.items()))
    return _sec("Утверждения", f"{warn}<p>Всего: {len(items)}</p><p>По типам: {t}</p><p>По статусам: {s}</p>")


def _options_block(d: Path) -> str:
    text = _read(d / "options.md")
    opts = OPT_RE.findall(text) if text else []
    if not opts:
        return _sec("Варианты", _empty())
    lis = "".join(f"<li><b>{_e(i)}</b> <span class=\"tag\">{_e(k)}</span> {_e(n)}</li>" for i, k, n in opts)
    choice = _section_md(text, "Выбор")
    ch = f"<p><b>Выбрано.</b> {_e(choice)}</p>" if choice else _empty("выбор ещё не сделан")
    return _sec("Варианты", f"<ul>{lis}</ul>{ch}")


def _cost_block(slug: str, st) -> str:
    try:
        c = status.costs(slug)
    except Exception:  # noqa: BLE001
        return _sec("Стоимость", _err("не удалось посчитать стоимость (log.jsonl). Что сделать: python tools/status.py"))
    rub = status._rub
    names = [("yandex", "Yandex"), ("env_model", "Модель среды"), ("search", "Поиск"), ("retries", "Повторы и сбои"), ("human", "Человек")]
    rows = "".join(f"<tr><td>{n}</td><td>{_e(rub(c[k]))}</td></tr>" for k, n in names)
    rows += f"<tr><td><b>Итого</b></td><td><b>{_e(rub(c['total']))}</b></td></tr>"
    body = f"<table>{rows}</table><p class=\"mut\">Минуты человека: {c['minutes']:g}</p>"
    if isinstance(st, dict):
        try:
            reds, yellows = status._degraded_lines(slug, status._scan(slug), st)
        except Exception:  # noqa: BLE001
            reds, yellows = [], []
        body += "".join(f'<p class="red">{_e(x)}</p>' for x in reds)
        body += "".join(f'<p class="yel">{_e(x)}</p>' for x in yellows)
    return _sec("Стоимость", body)


def _files_block(d: Path) -> str:
    parts = []
    if (d / "export" / "strategy.html").is_file():
        parts.append('<li><a href="export/strategy.html">Стратегия (export/strategy.html)</a></li>')
    rep = _read(d / "check-report.md")
    if rep is not None:
        m = re.search(r"Итог:[^\n]*", rep)
        verdict = f" — {_e(m.group(0))}" if m else ""
        parts.append(f'<li><a href="check-report.md">Отчёт проверки (check-report.md)</a>{verdict}</li>')
    return _sec("Результаты", f"<ul>{''.join(parts)}</ul>" if parts else _empty())


def render_panel(slug: str) -> str:
    d = project_path(slug)
    st, err = None, ""
    try:
        st, err = _load_state(slug)
    except Exception:  # noqa: BLE001
        st, err = None, "state.yaml не читается. Что сделать: исправь файл или возьми projects/_template/state.yaml."
    blocks = [_title_block(d, d.name), _steps_block(st, err)]
    if err:
        blocks.append(_sec("Ждёт от вас", _err(err)))
    else:
        blocks += [_waiting_block(st), _human_block(st)]
    blocks += [_questions_block(d), _sources_block(d), _claims_block(d), _options_block(d),
               _cost_block(d.name, st), _files_block(d),
               f'<p class="mut">Обновлено: {_e(now_iso())}</p>']
    return (f'<!doctype html>\n<html lang="ru"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Панель: {_e(d.name)}</title><style>{CSS}</style></head><body><main>"
            + "".join(blocks) + "</main></body></html>\n")


def _load_state(slug: str):
    from tools import state
    st, err = state.read_checked(slug)
    return st, err


def write_panel(slug: str) -> Path:
    out = project_path(slug) / "panel.html"
    write_text_atomic(out, render_panel(slug))
    return out


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(
        description="Панель проекта: одна HTML-страница «где мы» (шаги, что ждёт от вас, решения, вопросы, источники, "
                    "утверждения, варианты, стоимость). Результат: projects/<проект>/panel.html. Без сервера и интернета.",
        epilog="Коды выхода: 0 — готово, 1 — ошибка записи, 2 — неверные параметры, 3 — нет проекта.")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    ap.add_argument("--open", action="store_true", help="открыть панель в браузере")
    a = ap.parse_args(argv)
    try:
        slug = project_path(a.project).name
    except SystemExit:
        sys.exit(3)
    try:
        out = write_panel(slug)
    except OSError as e:
        die(f"не удалось записать файл ({e}). Что сделать: закрой файл в других программах и повтори.", code=1)
    print(f"Готово: {out}")
    if a.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
