# Журнал проекта (log.jsonl) и CLI учёта времени, цены, поисков: без него не посчитать стоимость и не воспроизвести ход работы.
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from tools.common import append_jsonl, now_iso, project_path, setup_stdio  # noqa: E402


def event(slug, kind: str, **fields) -> None:
    append_jsonl(project_path(slug) / "log.jsonl", {"ts": now_iso(), "kind": kind, **fields})


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(description="Запись в журнал проекта (log.jsonl).")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("human", help='время человека: <минуты> "<что делал>"')
    h.add_argument("minutes", type=float)
    h.add_argument("what")
    m = sub.add_parser("model", help="расход модели среды в USD")
    m.add_argument("usd", type=float)
    m.add_argument("--manual", action="store_true", help="сумма введена вручную, а не из ccusage")
    s = sub.add_parser("search", help="поисковый запрос, сделанный агентом")
    s.add_argument("query")
    s.add_argument("--engine", choices=["claude", "cursor", "opencode", "other"], default="other")
    n = sub.add_parser("note", help="произвольная заметка")
    n.add_argument("text")
    a = ap.parse_args(argv)
    slug = a.project
    if a.cmd == "human":
        event(slug, "human", minutes=a.minutes, what=a.what)
    elif a.cmd == "model":
        event(slug, "model", usd=a.usd, manual=a.manual)
    elif a.cmd == "search":
        event(slug, "search", query=a.query, engine=a.engine)
    else:
        event(slug, "note", text=a.text)
    print("Записано в журнал.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
