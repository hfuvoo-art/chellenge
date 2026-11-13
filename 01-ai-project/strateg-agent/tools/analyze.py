# analyze.py: детерминированные табличные факты (подкоманда cell): ячейка xlsx/csv → fact без участия LLM; без него числа из таблиц пришлось бы доверять модели.
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from tools import claims, ingest, tables  # noqa: E402
from tools.common import die, project_path, setup_stdio, sha256_file  # noqa: E402

WRITER = "analyze.py"


def add_cell_claim(slug, sid: str, locator: str, questions: list[str] | None = None) -> tuple[str, tables.Cell]:
    src = next((s for s in ingest._load_sources(slug) if s["id"] == sid), None)
    if src is None:
        raise ValueError(f"источника {sid} нет в проекте. Что сделать: `python tools/ingest.py <файл.xlsx> --found-by user`.")
    if src["kind"] != "table":
        raise ValueError(f"{sid} — {src['kind']}, а не таблица. Что сделать: для текста факты берёт extract.py.")
    path = project_path(slug) / "materials" / f"{sid}.{src['ext']}"
    if not path.is_file() or sha256_file(path) != src["sha256"]:
        raise ValueError(f"оригинал {sid} отсутствует или изменён. Что сделать: добавь таблицу заново через ingest.py.")
    cell = tables.get_cell(path, locator)
    rec = {
        # шапка не распознана → не fact, а estimate (docs/07): человек должен подтвердить толкование
        "type": "fact" if cell.header_ok else "estimate",
        "text": tables.render(cell),
        "source": sid,
        "locator": cell.locator,
        "quote": tables.render(cell),
        "dims": dict(cell.dims),
        "extracted_by": WRITER,
        "question": list(questions or []),
    }
    if not isinstance(cell.value, str):
        rec["value"] = cell.value
    return claims.add(slug, rec), cell


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(description="Детерминированный анализ таблиц проекта.")
    ap.add_argument("-p", "--project", help="имя проекта (по умолчанию текущий)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("cell", help="записать значение ячейки таблицы как fact (extracted_by: analyze.py)")
    s.add_argument("source", help="id источника, например S-005")
    s.add_argument("locator", help='ячейка вида "Лист!C14"')
    s.add_argument("--question", action="append", help="вопрос, к которому относится факт (например Q1); можно несколько раз")
    a = ap.parse_args(argv)
    try:
        cid, cell = add_cell_claim(a.project, a.source, a.locator, a.question)
    except ValueError as e:
        die(str(e))
    print(f"{cid}: {tables.render(cell)}")
    if not cell.header_ok:
        print(f"ВНИМАНИЕ: шапка ячейки не распознана ({tables.UNKNOWN_MARK}), записан estimate, а не fact. "
              f"Что сделать: проверить шапку в Excel и исправить файл либо подтвердить толкование расчётом calc/{cid}.py, "
              "иначе check.py даст FAIL по этому утверждению.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
