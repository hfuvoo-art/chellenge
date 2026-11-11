# Хук PostToolUse (Bash): пишет событие `tool` в log.jsonl проекта для команд `python tools/…`; без него в журнале нет следа запусков скриптов. Ключи маскируются.
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

TOOL_RE = re.compile(r"\bpython[\w.]*\s+(?:-\w+\s+)*(?:[^\s'\"]*[\\/])?tools[\\/](\w+)\.py\b", re.I)
MASKS = [
    (re.compile(r"(Bearer\s+)\S+", re.I), r"\1***"),
    (re.compile(r"\bAQVN[\w-]+"), "***"),
    (re.compile(r"\bsk-[\w-]{4,}"), "***"),
    (re.compile(r"(--?(?:api[-_]?key|token|secret|password|passwd|key)(?:=|\s+))\S+", re.I), r"\1***"),
    (re.compile(r"\b((?:\w*(?:api[_-]?key|token|secret|password))\s*[=:]\s*)\S+", re.I), r"\1***"),
]


def mask(s: str, limit: int = 300) -> str:
    for rx, rep in MASKS:
        s = rx.sub(rep, s)
    s = " ".join(s.split())
    return s if len(s) <= limit else s[:limit] + "…"


def current_project():
    from tools.common import current_slug, projects_dir
    slug = current_slug()
    return slug if slug and (projects_dir() / slug).is_dir() else None


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
        cmd = data["tool_input"]["command"]
        m = TOOL_RE.search(cmd) if isinstance(cmd, str) else None
        slug = current_project() if m else None
        if m and slug:
            from tools.log import event
            event(slug, "tool", script=f"{m.group(1)}.py", command=mask(cmd))
    except BaseException:  # noqa: BLE001 — хук не должен ронять сессию
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
