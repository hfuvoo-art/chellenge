# Общая заготовка проекта для тестов impact/review: без неё каждый тест собирал бы claims, options, strategy и decisions заново.
import json
from pathlib import Path

import yaml

from tools.common import project_path


def build(slug: str, decisions: list[dict] | None = None) -> Path:
    root = project_path(slug)
    claims = [
        {"id": "C-001", "type": "fact", "text": "Цена пакета 500 ₽", "source": "S-001", "locator": "p.1", "quote": "500 ₽", "status": "active", "supersedes": None},
        {"id": "C-002", "type": "fact", "text": "Срок 30 дней", "source": "S-001", "locator": "p.2", "quote": "30 дней", "status": "active", "supersedes": None},
        {"id": "C-003", "type": "fact", "text": "Поддержка 24/7", "source": "S-002", "locator": "p.1", "quote": "24/7", "status": "active", "supersedes": None},
        {"id": "C-004", "type": "fact", "text": "Старая цифра", "source": "S-003", "locator": "p.1", "quote": "старая", "status": "superseded", "status_by": "C-005", "supersedes": None},
        {"id": "C-005", "type": "fact", "text": "Новая цифра", "source": "S-003", "locator": "p.2", "quote": "новая", "status": "active", "supersedes": "C-004"},
        {"id": "C-006", "type": "fact", "text": "Не связано", "source": "S-004", "locator": "p.1", "quote": "x", "status": "active", "supersedes": None},
    ]
    (root / "claims.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in claims), encoding="utf-8")
    srcs = [{"id": "S-001", "supersedes": None}, {"id": "S-002", "supersedes": "S-001"},
            {"id": "S-003", "supersedes": None}, {"id": "S-004", "supersedes": None}]
    (root / "sources.yaml").write_text(yaml.safe_dump({"sources": srcs}), encoding="utf-8")
    (root / "options.md").write_text(
        "# Варианты\n\n## O1 · option · Первый\nСуть: цена [C-001].\n\n## O2 · close · Второй\nСуть: [C-004] и [C-006].\n\n## O3 · option · Третий\nСуть: [C-006].\n",
        encoding="utf-8")
    (root / "strategy.md").write_text(
        "# Стратегия\n\n## Рекомендация\n\n- Т1: решение [C-006]\n\n## Продуктовая стратегия\n\n### Альтернативы\n\nЦена [C-002].\n\n"
        "### Выбранное направление\n\nБез ссылок.\n\n## Коммуникационная стратегия\n\n### Обещания → функции продукта\n\n"
        "- «Пакет за 500 ₽» → F-1 (planned)\n- «Поддержка» → F-2 (planned)\n\n## Источники\n\n- S-001 — страница тарифов.\n",
        encoding="utf-8")
    (root / "product.yaml").write_text(yaml.safe_dump({"features": [
        {"id": "F-1", "what": "Пакет", "status": "planned", "available_from": "2027-Q1", "basis": ["C-001"]},
        {"id": "F-2", "what": "Поддержка", "status": "planned", "available_from": "2027-Q1", "basis": ["C-006"]},
    ]}, allow_unicode=True), encoding="utf-8")
    (root / "decisions.yaml").write_text(yaml.safe_dump({"decisions": decisions or [
        {"id": "D-1", "decision": "Запустить пакет", "owner": "Иван", "metric": "продажи", "basis": ["C-002"],
         "target": "100 в месяц", "deadline": "2027-03-01", "depends_on": [], "revisit_if": [], "status": "active"},
        {"id": "D-2", "decision": "Запустить поддержку", "owner": "Анна", "metric": "NPS", "basis": ["C-006"],
         "target": "4,5", "deadline": "2027-03-01", "depends_on": ["F-1"], "revisit_if": [], "status": "active"},
        {"id": "D-3", "decision": "Чужое", "owner": "Олег", "metric": "x", "basis": ["C-006"],
         "target": "y", "deadline": "2027-03-01", "depends_on": [], "revisit_if": [], "status": "active"},
    ]}, allow_unicode=True), encoding="utf-8")
    return root
