# Хук PostToolUse (WebSearch): пишет событие `search` в log.jsonl проекта; без него поиск не попадёт в статью стоимости «поиск». Ключи в запросе маскируются.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__, require_libs=False)


def main() -> int:
    try:
        from log_tool import current_project, mask
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
        q = data["tool_input"]["query"]
        slug = current_project() if isinstance(q, str) and q.strip() else None
        if slug:
            from tools.log import event
            event(slug, "search", query=mask(q, 500), engine="claude")
    except BaseException:  # noqa: BLE001 — хук не должен ронять сессию
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
