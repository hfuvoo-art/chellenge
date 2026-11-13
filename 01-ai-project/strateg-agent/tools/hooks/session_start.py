# Хук SessionStart: кладёт в контекст статус проекта (`status.py --hook`); без него агент начинает сессию, не зная шага, ожидания человека и красных строк.
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__, require_libs=False)
LIMIT = 9500  # лимит контекста хука — 10 000 символов


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    try:
        from tools.common import current_slug, projects_dir
        slug = current_slug()
        if not slug or not (projects_dir() / slug).is_dir():
            print("Проект не выбран. Начни с playbooks/1-frame.md (создать: `python tools/project.py new <имя>`); AGENTS.md — «Первое действие».")
            return 0
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "status.py"), "--hook"], cwd=str(ROOT), capture_output=True, timeout=25)
        out = r.stdout.decode("utf-8", errors="replace").strip()
        print(out[:LIMIT] if out else "Статус недоступен. Что сделать: `python tools/status.py`.")
    except BaseException:  # noqa: BLE001 — хук не должен ронять сессию
        print("Статус недоступен. Что сделать: `python tools/status.py`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
