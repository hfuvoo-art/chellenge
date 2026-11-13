# export.py: strategy.md → читаемый HTML/DOCX (сноски вместо [C-…], названия функций вместо F-n, метки гипотез); без него руководитель читает сырые id и не видит, на чём стоит вывод.
from __future__ import annotations

import argparse
import html
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from tools import check, claims  # noqa: E402
from tools.common import die, project_path, read_text, read_yaml, setup_stdio, write_text_atomic  # noqa: E402

FORMATS = ("html", "docx")
TYPE_LABELS = {"hypothesis": "гипотеза", "forecast": "прогноз", "synthetic": "синтетика"}
TYPE_NAMES = {"fact": "факт", "estimate": "оценка", "hypothesis": "гипотеза", "forecast": "прогноз", "synthetic": "синтетика",
              "interview": "интервью", "conclusion": "вывод агента", "observation": "наблюдение"}
REF_GROUP_RE = re.compile(r"\[(C-\d+(?:\s*[,;]\s*C-\d+)*)\]")
TOKEN_RE = re.compile(r"\[(C-\d+(?:\s*[,;]\s*C-\d+)*)\]|\b(C-\d+)\b|\b(F-\d+)\b|\*\*(.+?)\*\*")
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
REC, SOURCES = "Рекомендация", "Источники"


class ExportError(Exception):
    pass


def _clean(s) -> str:
    return CTRL_RE.sub("", str(s if s is not None else ""))


class _Ctx:
    """Данные проекта и нумерация сносок (по первому появлению в тексте)."""

    def __init__(self, slug: str):
        self.slug = slug
        self.claims = {c["id"]: c for c in claims.load(slug)}
        self.features, _ = check._features(slug)
        p = project_path(slug) / "sources.yaml"
        data = read_yaml(p) if p.is_file() else None
        self.sources = {str(s["id"]): s for s in ((data or {}).get("sources") or []) if isinstance(s, dict) and s.get("id")}
        self.notes: list[str] = []  # cid в порядке нумерации
        self.cited_sources: list[str] = []
        self.warnings: list[str] = []

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def ref(self, cid: str) -> tuple:
        c = self.claims.get(cid)
        if c is None:
            self.warn(f"{cid}: такого утверждения нет в claims.jsonl")
            return ("miss", cid, "нет в реестре")
        if c.get("status") == "retracted":
            self.warn(f"{cid}: утверждение отозвано")
            return ("miss", cid, "отозвано")
        if cid not in self.notes:
            self.notes.append(cid)
        src = c.get("source")
        if src and src not in self.cited_sources:
            self.cited_sources.append(src)
        if c.get("status") == "superseded":
            self.warn(f"{cid}: утверждение заменено более новым")
        return ("fn", self.notes.index(cid) + 1, cid)

    def feature(self, fid: str) -> tuple:
        f = self.features.get(fid)
        if f is None:
            self.warn(f"{fid}: функции нет в product.yaml")
            return ("feat", fid, "", "нет в product.yaml")
        if f.get("status") == "exists":
            st = "есть"
        else:
            af = f.get("available_from")
            st = f"планируется с {af}" if af else "планируется"
        return ("feat", fid, _clean(f.get("what") or fid), st)

    def inline(self, text: str) -> list[tuple]:
        """Текст → сегменты: ('t', s) | ('b', s) | ('fn', n, cid) | ('miss', cid, why) | ('label', s) | ('feat', id, name, status)."""
        out: list[tuple] = []
        pos = 0
        text = _clean(text)

        def cid_segs(cid: str):
            r = self.ref(cid)
            out.append(r)
            if r[0] == "fn":
                lab = TYPE_LABELS.get(self.claims[cid].get("type"))
                if lab:
                    out.append(("label", lab))
                if self.claims[cid].get("status") == "superseded":
                    out.append(("label", "устарело"))

        for m in TOKEN_RE.finditer(text):
            if m.start() > pos:
                out.append(("t", text[pos:m.start()]))
            if m.group(1):
                for cid in re.findall(r"C-\d+", m.group(1)):
                    cid_segs(cid)
            elif m.group(2):
                cid_segs(m.group(2))
            elif m.group(3):
                out.append(self.feature(m.group(3)))
            else:
                out.append(("b", m.group(4)))
            pos = m.end()
        if pos < len(text):
            out.append(("t", text[pos:]))
        return out


def _parse_blocks(text: str) -> list[dict]:
    blocks: list[dict] = []
    para: list[str] = []

    def flush():
        if para:
            blocks.append({"kind": "p", "text": " ".join(para)})
            para.clear()

    for ln in text.splitlines():
        h = check.HEAD_RE.match(ln)
        b = check.BULLET_RE.match(ln)
        if h:
            flush()
            blocks.append({"kind": f"h{len(h.group(1))}", "text": h.group(2)})
        elif b:
            flush()
            blocks.append({"kind": "li", "text": b.group(1)})
        elif not ln.strip():
            flush()
        else:
            para.append(ln.strip())
    flush()
    return blocks


def _split(blocks: list[dict]) -> tuple[str, list[dict], list[dict]]:
    """→ (заголовок, блоки рекомендации, прочие блоки без раздела «Источники»)."""
    title, rec, body = "Стратегия", [], []
    cur = None
    for b in blocks:
        if b["kind"] == "h1":
            title = b["text"]
            continue
        if b["kind"] == "h2":
            cur = check._norm_title(b["text"])
            if cur == check._norm_title(REC):
                continue
            if cur == check._norm_title(SOURCES):
                continue
        if cur == check._norm_title(REC):
            rec.append(b)
        elif cur == check._norm_title(SOURCES):
            continue
        else:
            body.append(b)
    return title, rec, body


def _src_line(ctx: _Ctx, sid: str) -> dict:
    s = ctx.sources.get(sid)
    if s is None:
        return {"id": sid, "title": "(нет в sources.yaml)", "where": "", "url": "", "as_of": ""}
    url = _clean(s.get("url") or "")
    where = url or (_clean(s.get("path") or "") and "файл " + _clean(s.get("path"))) or ""
    return {"id": sid, "title": _clean(s.get("title") or sid), "where": where,
            "url": url if re.match(r"^https?://", url) else "", "as_of": _clean(s.get("as_of") or "")}


def _note(ctx: _Ctx, cid: str) -> dict:
    c = ctx.claims[cid]
    n = {"cid": cid, "kind": TYPE_NAMES.get(c.get("type"), str(c.get("type"))), "text": _clean(c.get("text")),
         "quote": _clean(c.get("quote") or ""), "locator": _clean(c.get("locator") or ""), "src": None,
         "as_of": _clean(c.get("as_of") or ""), "status": c.get("status")}
    if c.get("source"):
        n["src"] = _src_line(ctx, c["source"])
        n["as_of"] = n["as_of"] or n["src"]["as_of"]
    return n


def build(slug: str) -> dict:
    p = project_path(slug) / "strategy.md"
    if not p.is_file():
        raise ExportError("в проекте нет strategy.md. Что сделать: сначала шаг 5 (`playbooks/5-strategy.md`), затем `python tools/check.py`.")
    text = check.COMMENT_RE.sub("", read_text(p))
    title, rec, body = _split(_parse_blocks(text))
    ctx = _Ctx(slug)
    summary = [{"kind": b["kind"], "segs": ctx.inline(b["text"])} for b in rec]
    blocks = [{"kind": b["kind"], "segs": ctx.inline(b["text"])} for b in body]
    return {"title": _clean(title), "summary": summary, "blocks": blocks,
            "notes": [_note(ctx, c) for c in ctx.notes],
            "sources": [_src_line(ctx, s) for s in sorted(ctx.cited_sources)],
            "warnings": ctx.warnings}


# ---------- HTML ----------

CSS = """body{font:16px/1.55 system-ui,Segoe UI,Arial,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a;background:#fff}
h1{font-size:1.7rem}h2{margin-top:2rem;border-bottom:1px solid #ddd;padding-bottom:.2rem}h3{margin-top:1.4rem}
.box{background:#eef4ff;border-left:4px solid #2a5bd7;padding:.6rem 1rem;margin:1rem 0}.box h2{margin:.2rem 0;border:0}
.warn{background:#fff3cd;border-left:4px solid #c79100;padding:.5rem 1rem;margin:1rem 0}
.miss{background:#ffd7d7;padding:0 .25rem;border-radius:3px}.label{font-size:.75rem;background:#ececec;border-radius:3px;padding:0 .3rem;margin-left:.15rem}
.feat{border-bottom:1px dotted #555}.fst{font-size:.8rem;color:#444}sup a{text-decoration:none}
ol.notes li{margin:.5rem 0}.quote{font-style:italic}.meta{color:#555;font-size:.9rem}"""


def _h(s) -> str:
    return html.escape(str(s), quote=True)


def _segs_html(segs) -> str:
    out = []
    for s in segs:
        k = s[0]
        if k == "t":
            out.append(_h(s[1]))
        elif k == "b":
            out.append(f"<strong>{_h(s[1])}</strong>")
        elif k == "fn":
            out.append(f'<sup><a id="r{s[1]}-{_h(s[2])}" href="#fn{s[1]}">[{s[1]}]</a></sup>')
        elif k == "miss":
            out.append(f'<span class="miss">[{_h(s[1])}: {_h(s[2])}]</span>')
        elif k == "label":
            out.append(f'<span class="label">{_h(s[1])}</span>')
        elif k == "feat":
            name = s[2] or s[1]
            out.append(f'<span class="feat">{_h(name)}</span> <span class="fst">({_h(s[1])}, {_h(s[3])})</span>'
                       if s[2] else f'<span class="miss">{_h(s[1])} ({_h(s[3])})</span>')
    return "".join(out)


def _blocks_html(blocks) -> str:
    out, in_ul = [], False
    for b in blocks:
        if b["kind"] != "li" and in_ul:
            out.append("</ul>")
            in_ul = False
        if b["kind"] == "li":
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_segs_html(b['segs'])}</li>")
        elif b["kind"] == "p":
            out.append(f"<p>{_segs_html(b['segs'])}</p>")
        else:
            lvl = min(max(int(b["kind"][1]), 2), 4)
            out.append(f"<h{lvl}>{_segs_html(b['segs'])}</h{lvl}>")
    if in_ul:
        out.append("</ul>")
    return "\n".join(out)


def _src_html(s) -> str:
    where = _h(s["where"])
    if s["url"]:
        where = f'<a href="{_h(s["url"])}" rel="noopener noreferrer">{where}</a>'
    parts = [f"{_h(s['id'])}: {_h(s['title'])}"]
    if where:
        parts.append(where)
    parts.append("на дату: " + (_h(s["as_of"]) or "не указана"))
    return ", ".join(parts)


def render_html(d: dict) -> str:
    o = ["<!doctype html>", '<html lang="ru"><head><meta charset="utf-8">',
         '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">',
         f"<title>{_h(d['title'])}</title><style>{CSS}</style></head><body>", f"<h1>{_h(d['title'])}</h1>"]
    if d["warnings"]:
        o.append('<div class="warn"><strong>Предупреждения при выгрузке:</strong><ul>'
                 + "".join(f"<li>{_h(w)}</li>" for w in d["warnings"]) + "</ul></div>")
    o.append('<div class="box"><h2>Решение за 1 минуту</h2>' + (_blocks_html(d["summary"]) or "<p>Раздел «Рекомендация» пуст.</p>") + "</div>")
    o.append(_blocks_html(d["blocks"]))
    if d["notes"]:
        o.append("<h2>Сноски</h2><ol class=\"notes\">")
        for i, n in enumerate(d["notes"], 1):
            body = f'<span class="label">{_h(n["kind"])}</span> '
            if n["quote"]:
                body += f'<span class="quote">«{_h(n["quote"])}»</span>'
            else:
                body += _h(n["text"])
            meta = []
            if n["src"]:
                meta.append("источник: " + _src_html(n["src"]))
            if n["locator"]:
                meta.append("место: " + _h(n["locator"]))
            if n["as_of"]:
                meta.append("на дату: " + _h(n["as_of"]))
            if n["status"] == "superseded":
                meta.append("утверждение заменено более новым")
            o.append(f'<li id="fn{i}">{body}<div class="meta">{_h(n["cid"])}; ' + "; ".join(meta) + "</div></li>")
        o.append("</ol>")
    o.append("<h2>Источники</h2>")
    o.append("<ul>" + "".join(f"<li>{_src_html(s)}</li>" for s in d["sources"]) + "</ul>" if d["sources"] else "<p>Источники не цитируются.</p>")
    o.append("</body></html>")
    return "\n".join(o) + "\n"


# ---------- DOCX ----------

def _segs_docx(par, segs) -> None:
    for s in segs:
        k = s[0]
        if k == "t":
            par.add_run(s[1])
        elif k == "b":
            par.add_run(s[1]).bold = True
        elif k == "fn":
            par.add_run(f"[{s[1]}]").font.superscript = True
        elif k == "miss":
            r = par.add_run(f"[{s[1]}: {s[2]}]")
            r.bold = True
        elif k == "label":
            r = par.add_run(f" ({s[1]})")
            r.italic = True
        elif k == "feat":
            if s[2]:
                par.add_run(s[2]).bold = True
                par.add_run(f" ({s[1]}, {s[3]})").italic = True
            else:
                par.add_run(f"{s[1]} ({s[3]})").bold = True


def _blocks_docx(doc, blocks) -> None:
    for b in blocks:
        if b["kind"] == "li":
            par = doc.add_paragraph(style="List Bullet")
        elif b["kind"] == "p":
            par = doc.add_paragraph()
        else:
            par = doc.add_heading(level=min(max(int(b["kind"][1]), 2), 4))
        _segs_docx(par, b["segs"])


def _src_text(s) -> str:
    parts = [f"{s['id']}: {s['title']}"]
    if s["where"]:
        parts.append(s["where"])
    parts.append("на дату: " + (s["as_of"] or "не указана"))
    return ", ".join(parts)


def render_docx(d: dict, out: Path) -> None:
    from docx import Document

    doc = Document()
    doc.add_heading(d["title"], level=1)
    if d["warnings"]:
        par = doc.add_paragraph()
        par.add_run("Предупреждения при выгрузке: " + "; ".join(d["warnings"])).bold = True
    doc.add_heading("Решение за 1 минуту", level=2)
    if d["summary"]:
        _blocks_docx(doc, d["summary"])
    else:
        doc.add_paragraph("Раздел «Рекомендация» пуст.")
    _blocks_docx(doc, d["blocks"])
    if d["notes"]:
        doc.add_heading("Сноски", level=2)
        for i, n in enumerate(d["notes"], 1):
            par = doc.add_paragraph()
            par.add_run(f"[{i}] ").bold = True
            par.add_run(f"({n['kind']}) ").italic = True
            par.add_run(f"«{n['quote']}»" if n["quote"] else n["text"])
            meta = [n["cid"]]
            if n["src"]:
                meta.append("источник: " + _src_text(n["src"]))
            if n["locator"]:
                meta.append("место: " + n["locator"])
            if n["as_of"]:
                meta.append("на дату: " + n["as_of"])
            if n["status"] == "superseded":
                meta.append("утверждение заменено более новым")
            par.add_run("\n" + "; ".join(meta))
    doc.add_heading("Источники", level=2)
    if d["sources"]:
        for s in d["sources"]:
            doc.add_paragraph(_src_text(s), style="List Bullet")
    else:
        doc.add_paragraph("Источники не цитируются.")
    fd, tmp = tempfile.mkstemp(dir=out.parent, suffix=".tmp")
    os.close(fd)
    try:
        doc.save(tmp)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def export(slug: str | None, fmt: str = "html", warnings: list | None = None) -> Path:
    """Собрать projects/<slug>/export/strategy.<fmt>. Предупреждения (неизвестные id и т.п.) добавляются в `warnings`, если он передан."""
    if fmt not in FORMATS:
        raise ExportError(f"формат «{fmt}» не поддерживается. Что сделать: `--format html` или `--format docx`.")
    root = project_path(slug)
    d = build(root.name)
    if warnings is not None:
        warnings.extend(d["warnings"])
    out = root / "export" / f"strategy.{fmt}"
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "html":
        write_text_atomic(out, render_html(d))
    else:
        render_docx(d, out)
    return out


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(
        description="Читаемая стратегия: превращает strategy.md в один HTML-файл или DOCX. Ссылки [C-…] становятся сносками "
                    "(цитата, источник, дата), F-n — названиями функций со статусом, гипотезы, прогнозы и синтетика помечены. "
                    "Результат: projects/<проект>/export/strategy.<формат>.",
        epilog="Коды выхода: 0 — готово, 1 — нет strategy.md или ошибка записи, 2 — неверные параметры, 3 — нет проекта. "
               "Неизвестные и отозванные [C-…] помечаются в тексте и печатаются как предупреждения.")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    ap.add_argument("--format", default="html", choices=FORMATS, help="html (по умолчанию) или docx")
    a = ap.parse_args(argv)
    try:
        slug = project_path(a.project).name
    except SystemExit:
        sys.exit(3)
    warns: list[str] = []
    try:
        out = export(slug, a.format, warns)
    except ExportError as e:
        die(str(e), code=1)
    except OSError as e:
        die(f"не удалось записать файл ({e}). Что сделать: закрой файл в других программах и повтори.", code=1)
    for w in warns:
        print(f"Предупреждение: {w}. Что сделать: поправь ссылку в strategy.md и повтори выгрузку.", file=sys.stderr)
    print(f"Готово: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
