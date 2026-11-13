# Хук PreToolUse: просит подтверждение, когда правка или команда затрагивает запертые файлы (У6); без него rules/, prompts/, methods/, AGENTS.md, CLAUDE.md, check.py и lock.py меняются молча. Предохранитель от случайной правки: обходы через cd, heredoc и скрипты regex-ом не закрыть, настоящая защита — rules.lock и check.py п.11.
import json
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__, require_libs=False)

DIRS = ("rules", "prompts", "methods")
FILES = ("agents.md", "claude.md", "tools/lock.py", "tools/check.py")
# Запертый путь в тексте команды (регистр не важен, слэш любой). Каталоги rules/prompts/methods считаются только
# в начале пути, после `./`, `../`, `x/../` или после корня агента (абсолютный путь), а не после любого `/`.
_ROOT_PFX = r"(?:[^\s\x27\x22]*?[\\/])?" + re.escape(ROOT.name) + r"[\\/]"
_LOCAL_PFX = r"(?:\.\.?[\\/]|[\w-]+[\\/]\.\.[\\/])*"
_ITEM = r"(?:(?:rules|prompts|methods)[\\/]|AGENTS\.md|CLAUDE\.md|tools[\\/]lock\.py|tools[\\/]check\.py)"
PROT_BODY = r"(?:" + _ROOT_PFX + r"|" + _LOCAL_PFX + r")" + _ITEM
PROT_RE = re.compile(r"(?<![\w.\\/-])" + PROT_BODY, re.I)
GIT_BARE = re.compile(r"(?<![\w.\\/-])(?:rules|prompts|methods|AGENTS\.md|CLAUDE\.md)(?![\w.-])", re.I)
GIT_WRITE = re.compile(r"\bgit\s+(?:checkout|restore|rm|mv|reset|clean|stash|apply|am)\b", re.I)
WRITE_PATTERNS = [
    re.compile(r"(?<![&>])\d?>>?\s*['\"]?" + PROT_BODY, re.I),  # > и >> в запертый путь (в том числе `x>rules/a`)
    re.compile(r"\b(?:sed|perl)\b[^|;&]*\s(?:-[A-Za-z]*i|--in-place)", re.I),
    re.compile(r"(?:^|[\s'\"(])(?:rm|rmdir|mv|tee|truncate|shred|del|erase|ren|rename|move|move-item|remove-item|"
               r"set-content|add-content|out-file|clear-content|new-item|copy-item|install|sc|ac)\b", re.I),
    GIT_WRITE,
    re.compile(r"\bdd\b[^|;&]*\bof=", re.I),
    re.compile(r"\bpython[\w.]*\s+-c\b.*(?:open\s*\([^)]*['\"][wax][bt+]*['\"]|write_text|write_bytes|unlink|remove|rename|replace\()", re.I | re.S),
    re.compile(r"\block\.py\b[^|;&]*--update", re.I),  # узаконивание правки запертых файлов подтверждает человек
]
CP_RE = re.compile(r"(?:^|\s)(?:cp|copy|xcopy|rsync|ln)\b", re.I)
SHELLS = ("Bash", "PowerShell")
# Оболочка или интерпретатор с кодом в кавычках (`pwsh -c '…'`, `python -c "…"`): кавычки — это команда, их не вырезаем.
INNER_RE = re.compile(r"^\s*(?:&\s*)?(?:pwsh|powershell|bash|sh|zsh|cmd|python[\w.]*)(?:\.exe)?\b[^'\"]*?\s(?:-c|-command|/c)\b", re.I)
# Остальное в кавычках — данные (сообщение коммита, JSON утверждения), кроме цели редиректа `> "rules/a.md"`.
QUOTED_RE = re.compile(r"(?<!>)(?<!> )('[^']*'|\"[^\"]*\")")


def _code_part(seg: str) -> str:
    return seg if INNER_RE.search(seg) else QUOTED_RE.sub("''", seg)


def _norm_path(p):
    """Путь относительно корня агента (posix, нижний регистр) или None, если файл вне корня."""
    if not isinstance(p, str) or not p.strip():
        return None
    q = Path(p.strip())
    if q.is_absolute():
        try:
            q = q.resolve().relative_to(ROOT.resolve())
        except (ValueError, OSError):
            return None
    else:
        try:
            q = (ROOT / q).resolve().relative_to(ROOT.resolve())
        except (ValueError, OSError):
            return None
    parts = [x for x in PurePosixPath(q.as_posix()).parts if x not in (".", "")]
    if ".." in parts:
        return None
    return "/".join(parts).lower()


def protected_file(p) -> bool:
    rel = _norm_path(p)
    return bool(rel) and (rel in FILES or (rel.split("/")[0] in DIRS and "/" in rel))


def _segments(cmd: str) -> list[str]:
    """Делит команду по ; && || | и переводам строк вне кавычек."""
    out, cur, quote, i = [], [], None, 0
    while i < len(cmd):
        ch = cmd[i]
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            cur.append(ch)
        elif ch in ";\n|" or cmd[i:i + 2] == "&&":
            out.append("".join(cur))
            cur = []
            if cmd[i:i + 2] in ("&&", "||"):
                i += 1
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return [s.strip() for s in out if s.strip()]


def bash_touches(cmd) -> bool:
    if not isinstance(cmd, str) or not (PROT_RE.search(cmd) or GIT_BARE.search(cmd)):
        return False
    for seg in _segments(cmd):
        code = _code_part(seg)  # глаголы записи ищем только вне строк-данных
        if GIT_WRITE.search(code) and GIT_BARE.search(seg):
            return True
        if not PROT_RE.search(seg):
            continue
        if any(p.search(code) for p in WRITE_PATTERNS):
            return True
        if CP_RE.search(seg):  # копирование: опасна только цель (последний аргумент)
            last = re.split(r"\s+", seg.rstrip())[-1].strip("'\"")
            if PROT_RE.search(last):
                return True
    # `x | tee rules/a.md`: tee в отдельном сегменте, путь в нём же, поэтому уже пойман выше
    return False


def decide(data) -> bool:
    if not isinstance(data, dict):
        return False
    ti = data.get("tool_input")
    if not isinstance(ti, dict):
        return False
    tool = data.get("tool_name")
    if tool in ("Edit", "Write", "MultiEdit"):
        return protected_file(ti.get("file_path") or ti.get("path"))
    if tool in SHELLS:
        return bash_touches(ti.get("command"))
    return False


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
        if decide(data):
            reason = ("Файл под замком rules.lock (rules/, prompts/, methods/, AGENTS.md, CLAUDE.md, tools/check.py, tools/lock.py): "
                      "его меняет только человек по явной просьбе. После правки нужен `python tools/lock.py --update --reason \"...\"`.")
            out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": reason}}
            sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
            sys.stdout.flush()
    except BaseException:  # noqa: BLE001 — хук не должен ронять сессию
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
