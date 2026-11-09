# Общие функции (пути, UTF-8, атомарная запись, id, хеши): без них каждый CLI по-своему ломается на кириллице и обрывах записи.
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

ROOT: Path = Path(__file__).resolve().parent.parent
MSK = timezone(timedelta(hours=3))


def die(msg: str, code: int = 1) -> NoReturn:
    print(f"Ошибка: {msg}", file=sys.stderr)
    sys.exit(code)


def setup_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def projects_dir() -> Path:
    env = os.environ.get("STRATEG_PROJECTS_DIR")
    return Path(env) if env else ROOT / "projects"


def read_text(p: Path | str) -> str:
    return Path(p).read_text(encoding="utf-8")


def current_slug() -> str | None:
    cur = projects_dir() / "CURRENT"
    if not cur.is_file():
        return None
    return read_text(cur).strip() or None


def project_path(slug: str | None = None) -> Path:
    if slug is None:
        slug = current_slug()
        if slug is None:
            die("текущий проект не выбран. Что сделать: `python tools/project.py new <имя>` или `project.py use <имя>`.")
    p = projects_dir() / slug
    if not p.is_dir():
        die(f"проекта «{slug}» нет. Что сделать: `python tools/project.py list`, затем `project.py use <имя>` или `new <имя>`.")
    return p


def write_text_atomic(p: Path | str, s: str) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(s.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_yaml(p: Path | str) -> Any:
    return yaml.safe_load(read_text(p))


def write_yaml_atomic(p: Path | str, data: Any) -> None:
    write_text_atomic(p, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False))


def append_jsonl(p: Path | str, obj: dict) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with open(p, "ab") as f:
        f.write(line.encode("utf-8"))
        f.flush()
        os.fsync(f.fileno())


def read_jsonl(p: Path | str) -> list[dict]:
    p = Path(p)
    if not p.is_file():
        return []
    return [json.loads(line) for line in read_text(p).splitlines() if line.strip()]


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path | str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(MSK).isoformat(timespec="seconds")


def next_id(prefix: str, existing, width: int = 3) -> str:
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    nums = [int(m.group(1)) for e in existing if (m := pat.match(str(e)))]
    return f"{prefix}-{(max(nums) + 1 if nums else 1):0{width}d}"


_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(u: str) -> str:
    parts = urlsplit(u.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    netloc = host
    if parts.port and parts.port != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{parts.port}"
    path = parts.path.rstrip("/")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")))
    return urlunsplit((scheme, netloc, path, query, ""))
