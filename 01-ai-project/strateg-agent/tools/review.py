# Поддержка решений: просрочки, устаревшие основания и сработавшие условия пересмотра из decisions.yaml; без него решение устаревает незаметно, а статус молчит.
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

import yaml  # noqa: E402

from tools import claims  # noqa: E402
from tools.common import project_path, read_yaml, setup_stdio  # noqa: E402

OPEN_STATUSES = ("active", "revisit")  # done и dropped не пересматриваются
DEAD_CLAIM = ("retracted", "disputed", "superseded")
ID_RE = re.compile(r"\b([CS]-\d+)\b")
KINDS = ("overdue", "stale_basis", "revisit")


@dataclass(frozen=True)
class ReviewItem:
    kind: str  # overdue | stale_basis | revisit
    decision_id: str
    msg: str


def load_decisions(slug) -> list[dict]:
    """Решения из decisions.yaml; пустой файл и `decisions: []` дают []. Битый YAML — ValueError с подсказкой."""
    p = project_path(slug) / "decisions.yaml"
    if not p.is_file():
        return []
    try:
        data = read_yaml(p)
    except yaml.YAMLError as e:
        raise ValueError(f"decisions.yaml не разобран ({type(e).__name__}). Что сделать: исправь YAML по шаблону projects/_template/decisions.yaml.") from e
    items = data.get("decisions") if isinstance(data, dict) else None
    return [d for d in (items or []) if isinstance(d, dict) and d.get("id")]


def superseded_sources(slug) -> dict[str, str]:
    """{старый S-id: S-id новой версии} по полю supersedes в sources.yaml."""
    p = project_path(slug) / "sources.yaml"
    if not p.is_file():
        return {}
    try:
        data = read_yaml(p)
    except yaml.YAMLError:
        return {}
    rows = data.get("sources") if isinstance(data, dict) else data
    out = {}
    for s in rows or []:
        if isinstance(s, dict) and s.get("id") and s.get("supersedes"):
            out[str(s["supersedes"])] = str(s["id"])
    return out


def _date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except ValueError:
        return None


def _strs(v) -> list[str]:
    if v is None:
        return []
    return [str(x) for x in (v if isinstance(v, list) else [v])]


def review(slug: str | None = None, today: date | None = None) -> list[ReviewItem]:
    """Пункты блока «Пересмотр»: overdue (срок прошёл), stale_basis (основание отозвано, оспорено или заменено), revisit (сработало revisit_if или статус revisit)."""
    today = today or date.today()
    status = {c["id"]: c.get("status") for c in claims.load(slug)}
    old_src = superseded_sources(slug)
    out: list[ReviewItem] = []
    for d in load_decisions(slug):
        did = str(d["id"])
        st = str(d.get("status") or "active")
        if st not in OPEN_STATUSES:
            continue
        dl = _date(d.get("deadline"))
        if st == "active" and dl is not None and dl < today:
            out.append(ReviewItem("overdue", did, f"срок {dl.isoformat()} прошёл ({(today - dl).days} дн.). Что сделать: назвать итог по метрике «{d.get('metric') or '?'}» или перенести срок."))
        for cid in _strs(d.get("basis")):
            cs = status.get(cid)
            if cs is None:
                out.append(ReviewItem("stale_basis", did, f"основания {cid} нет в реестре. Что сделать: заменить основание на существующее утверждение."))
            elif cs in DEAD_CLAIM:
                out.append(ReviewItem("stale_basis", did, f"основание {cid} имеет статус {cs}. Что сделать: `impact.py --claim {cid}`, затем пересмотреть решение."))
        reasons = []
        if st == "revisit":
            reasons.append("статус revisit")
        for cond in _strs(d.get("revisit_if")):
            for ref in dict.fromkeys(ID_RE.findall(cond)):
                if ref.startswith("C-") and status.get(ref) in DEAD_CLAIM:
                    reasons.append(f"{ref} стало {status[ref]}: «{cond}»")
                elif ref.startswith("S-") and ref in old_src:
                    reasons.append(f"источник {ref} заменён версией {old_src[ref]}: «{cond}»")
        for r in reasons:
            out.append(ReviewItem("revisit", did, f"{r}. Что сделать: решить, меняется ли решение (`impact.py`)."))
    return out


def format_items(items: list[ReviewItem]) -> list[str]:
    return [f"{i.kind} {i.decision_id}: {i.msg}" for i in items]


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(description="Поддержка решений: просроченные решения, устаревшие основания, сработавшие условия пересмотра (decisions.yaml).")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    ap.add_argument("--today", help="дата отсчёта ГГГГ-ММ-ДД (по умолчанию сегодня)")
    a = ap.parse_args(argv)
    today = None
    if a.today:
        today = _date(a.today)
        if today is None:
            print("Дата --today не разобрана. Что сделать: формат ГГГГ-ММ-ДД.")
            return 3
    try:
        items = review(a.project, today)
    except ValueError as e:
        print(e)
        return 3
    print("\n".join(format_items(items)) if items else "Пересмотр не нужен: просрочек и устаревших оснований нет.")
    return 1 if items else 0


if __name__ == "__main__":
    sys.exit(main())
