# Состояние проекта (state.yaml): шаг, выполненные action_id, ожидание человека. Без него повторный запуск после обрыва дублирует работу.
from __future__ import annotations

import copy
import json

from tools.common import now_iso, project_path, read_yaml, sha256_text, write_yaml_atomic
from tools.log import event

_DEFAULT = {"step": {"n": 0, "name": "not-started"}, "done": {}, "waiting": None, "human": [], "degraded": []}


def load(slug: str | None) -> dict:
    p = project_path(slug) / "state.yaml"
    st = (read_yaml(p) if p.is_file() else None) or {}
    for k, v in _DEFAULT.items():
        if st.get(k) is None and k != "waiting":
            st[k] = copy.deepcopy(v)
    st.setdefault("waiting", None)
    return st


def save(slug: str | None, st: dict) -> None:
    write_yaml_atomic(project_path(slug) / "state.yaml", st)


def action_id(step: str, unit: str, payload) -> str:
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f"{step}:{unit}:{sha256_text(payload)[:12]}"


def is_done(slug: str | None, aid: str) -> bool:
    return aid in load(slug)["done"]


def mark_done(slug: str | None, aid: str, meta: dict | None = None) -> None:
    st = load(slug)
    if aid in st["done"]:
        return
    st["done"][aid] = {"at": now_iso(), **(meta or {})}
    save(slug, st)


def set_step(slug: str | None, n: int, name: str) -> None:
    st = load(slug)
    st["step"] = {"n": n, "name": name}
    save(slug, st)
    event(slug, "step", n=n, name=name)


def wait_human(slug: str | None, point: str, question: str) -> None:
    st = load(slug)
    st["waiting"] = {"point": point, "question": question, "since": now_iso()}
    save(slug, st)
    event(slug, "wait_human", point=point, question=question)


def resolve_human(slug: str | None, point: str, summary: str, minutes: float) -> None:
    st = load(slug)
    st["waiting"] = None
    st["human"].append({"point": point, "summary": summary, "minutes": minutes, "at": now_iso()})
    save(slug, st)
    event(slug, "human", point=point, summary=summary, minutes=minutes)


def add_degraded(slug: str | None, flag: str, note: str) -> None:
    st = load(slug)
    if not any(d.get("flag") == flag and d.get("note") == note for d in st["degraded"]):
        st["degraded"].append({"flag": flag, "note": note, "at": now_iso()})
        save(slug, st)
    event(slug, "degraded", flag=flag, note=note)
