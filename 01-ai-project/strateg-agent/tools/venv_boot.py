# Автопоиск .venv: без него скрипты и хуки, запущенные системным python (окно Claude Code, Cursor), не видят библиотек агента и падают, а человеку приходится в терминале активировать окружение. Только стандартная библиотека.
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD_ENV = "STRATEG_VENV_BOOT"
NO_LIBS_MSG = ("Библиотеки агента не установлены. Что сделать: попросите агента выполнить установку "
               "(README, «Первый запуск») или `python -m venv .venv` и `.venv/Scripts/pip install -r requirements.txt` "
               "(macOS и Linux: `.venv/bin/pip`).")


def venv_python(root: Path | None = None) -> Path | None:
    """Интерпретатор .venv рядом с папкой агента или None."""
    base = (root or ROOT) / ".venv"
    py = base / "Scripts" / "python.exe" if os.name == "nt" else base / "bin" / "python"
    return py if py.is_file() else None


def _is_venv_active(py: Path) -> bool:
    try:
        if Path(sys.prefix).resolve() == py.parent.parent.resolve():
            return True
        return Path(sys.executable).resolve() == py.resolve()
    except OSError:
        return False


def _is_entry_script(script: str | None) -> bool:
    """True, только если скрипт запущен как программа (не импортирован тестами или другим кодом)."""
    if script is None:
        return True
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if not main_file:
        return False
    try:
        return Path(main_file).resolve() == Path(script).resolve()
    except OSError:
        return False


def ensure_venv(script: str | None = None, require_libs: bool = True, root: Path | None = None) -> None:
    """Перезапускает скрипт интерпретатором .venv; нет .venv и нет библиотек — понятная ошибка, код 3.

    script — `__file__` вызывающего скрипта (при импорте из тестов ничего не делает).
    require_libs=False — для хуков: не падать, если библиотек нет, только перезапуститься в .venv при наличии.
    """
    if not _is_entry_script(script):
        return
    py = venv_python(root)
    if py is not None:
        if _is_venv_active(py) or os.environ.get(GUARD_ENV):
            return
        env = {**os.environ, GUARD_ENV: "1"}
        r = subprocess.run([str(py), str(Path(script or sys.argv[0]).resolve()), *sys.argv[1:]], env=env)
        sys.exit(r.returncode)
    if require_libs and importlib.util.find_spec("yaml") is None:
        print(NO_LIBS_MSG, file=sys.stderr)
        sys.exit(3)
