# rules.lock: sha256 запертых файлов (rules/**, prompts/**, methods/**, AGENTS.md, CLAUDE.md, tools/check.py, tools/lock.py) и история правок; без него подмену правил или проверяющего никто не заметит. Запираемый файл (У6): это обнаружение, а не запрет.
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from tools.common import ROOT, current_slug, now_iso, projects_dir, read_yaml, setup_stdio, write_yaml_atomic  # noqa: E402

LOCK_NAME = "rules.lock"
LOCKED_DIRS = ("rules", "prompts", "methods")
LOCKED_FILES = ("AGENTS.md", "CLAUDE.md", "tools/check.py", "tools/lock.py")
IGNORED_PARTS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".tmp"}


def _sha(p: Path) -> str:
    data = p.read_bytes().replace(b"\r\n", b"\n")  # CRLF/LF не должны давать ложную тревогу на Windows
    return hashlib.sha256(data).hexdigest()


def compute(root) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    for d in LOCKED_DIRS:
        base = root / d
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file() and not (IGNORED_PARTS & set(p.parts)) and p.suffix not in IGNORED_SUFFIXES:
                    out[p.relative_to(root).as_posix()] = _sha(p)
    for f in LOCKED_FILES:
        p = root / f
        if p.is_file():
            out[f] = _sha(p)
    return out


def _load(root: Path) -> dict:
    p = root / LOCK_NAME
    return (read_yaml(p) or {}) if p.is_file() else {}


def _diff(old: dict[str, str], new: dict[str, str]) -> list[str]:
    return ([f"изменён: {k}" for k in sorted(new) if k in old and old[k] != new[k]]
            + [f"новый: {k}" for k in sorted(new) if k not in old]
            + [f"удалён: {k}" for k in sorted(old) if k not in new])


def verify(root) -> list[str]:
    root = Path(root)
    if not (root / LOCK_NAME).is_file():
        return [f"нет файла {LOCK_NAME}"]
    return _diff(_load(root).get("files") or {}, compute(root))


def update(root, reason: str) -> list[str]:
    """Пересчитывает хеши, дописывает в историю {updated_at, reason, changed}; возвращает список изменённых путей."""
    root = Path(root)
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("нужна причина обновления (--reason)")
    data = _load(root)
    old, new = data.get("files") or {}, compute(root)
    changed = [line.split(": ", 1)[1] for line in _diff(old, new)]
    entry = {"updated_at": now_iso(), "reason": reason, "changed": changed}
    write_yaml_atomic(root / LOCK_NAME, {"files": new, "history": list(data.get("history") or []) + [entry]})
    slug = current_slug()
    if slug and (projects_dir() / slug).is_dir():
        from tools.log import event
        event(slug, "lock_update", reason=reason, changed=changed)
    return changed


def last_update(root) -> dict | None:
    """Последняя запись истории (для status.py)."""
    hist = _load(Path(root)).get("history") or []
    return hist[-1] if hist else None


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(description="Проверка и обновление rules.lock (правила, промпты, методики, AGENTS.md, CLAUDE.md, check.py, lock.py).",
                                 epilog="Коды выхода: 0 — OK, 1 — файлы не совпадают с rules.lock, 3 — ошибка использования.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--verify", action="store_true", help="сверить файлы с rules.lock")
    g.add_argument("--update", action="store_true", help="пересчитать хеши и записать в историю")
    ap.add_argument("--reason", help="причина обновления (обязательна для --update)")
    ap.add_argument("--root", default=str(ROOT), help="папка агента (по умолчанию текущая установка)")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if a.verify:
        problems = verify(root)
        if problems:
            print("Правила не совпадают с rules.lock:")
            for p in problems:
                print(f"  {p}")
            print("Что сделать: если правка твоя и осознанная — `python tools/lock.py --update --reason \"…\"`; иначе верни файлы.")
            return 1
        print("OK: правила совпадают с rules.lock.")
        return 0
    if not (a.reason or "").strip():
        print("Ошибка: для --update нужна причина. Что сделать: добавь --reason \"что и зачем изменено\".", file=sys.stderr)
        return 3
    changed = update(root, a.reason)
    print(f"rules.lock обновлён. Изменено файлов: {len(changed)}" + (f" ({', '.join(changed)})" if changed else "") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
