# Проекты (projects/<slug>, CURRENT): создаёт папку из шаблона и выбирает текущий проект; без него нет места для состояния задачи.
import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from tools.common import (  # noqa: E402
    ROOT, current_slug, die, now_iso, projects_dir, read_yaml, setup_stdio, write_text_atomic, write_yaml_atomic,
)

TEMPLATE = ROOT / "projects" / "_template"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def cmd_new(slug: str) -> None:
    if not SLUG_RE.match(slug):
        die(f"имя «{slug}» не подходит. Что сделать: латиница, цифры, «-» и «_», например `esim-travel`.")
    dst = projects_dir() / slug
    if dst.exists():
        die(f"проект «{slug}» уже есть. Что сделать: `project.py use {slug}` или другое имя.")
    shutil.copytree(TEMPLATE, dst)
    st = read_yaml(dst / "state.yaml") or {}
    st["created"] = now_iso()
    write_yaml_atomic(dst / "state.yaml", st)
    write_text_atomic(projects_dir() / "CURRENT", slug + "\n")
    print(f"Проект «{slug}» создан и выбран текущим: {dst}")


def cmd_use(slug: str) -> None:
    if slug.startswith("_") or not (projects_dir() / slug).is_dir():
        die(f"проекта «{slug}» нет. Что сделать: `project.py list`.")
    write_text_atomic(projects_dir() / "CURRENT", slug + "\n")
    print(f"Текущий проект: {slug}")


def cmd_list() -> None:
    pd = projects_dir()
    slugs = sorted(p.name for p in pd.iterdir() if p.is_dir() and not p.name.startswith("_")) if pd.is_dir() else []
    cur = current_slug()
    if cur and cur not in slugs:
        print(f"Предупреждение: CURRENT указывает на несуществующий проект «{cur}». Что сделать: `project.py use <имя>`.",
              file=sys.stderr)
        cur = None
    if not slugs:
        print("Проектов нет. Что сделать: `python tools/project.py new <имя>`.")
        return
    print("Проекты (* — текущий):")
    for s in slugs:
        print(f"{'*' if s == cur else ' '} {s}")


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(description="Управление проектами стратега.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("new", help="создать проект из шаблона и сделать текущим").add_argument("slug")
    sub.add_parser("use", help="сделать проект текущим").add_argument("slug")
    sub.add_parser("list", help="показать проекты")
    a = ap.parse_args(argv)
    if a.cmd == "new":
        cmd_new(a.slug)
    elif a.cmd == "use":
        cmd_use(a.slug)
    else:
        cmd_list()
    return 0


if __name__ == "__main__":
    sys.exit(main())
