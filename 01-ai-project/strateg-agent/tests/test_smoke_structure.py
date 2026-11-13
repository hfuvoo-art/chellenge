# Дымовой тест структуры документов (У18): разделы playbooks, шаблон methods, CLI в AGENTS.md, ссылки SKILL.md; без него содержание агента тихо расходится с кодом.
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYBOOKS = ["1-frame", "2-collect", "3-research", "4-options", "5-strategy", "6-after-decision"]
COMMON = ["Вход", "Действия", "Выход", "Критерий готовности", "Типичные ошибки"]
HUMAN_POINT = {"1-frame", "4-options", "5-strategy"}  # точки человека 1, 2, 3
METHOD_H2 = ["Когда применять", "Вход", "Шаги", "Выход", "Критерии качества", "Типичные ошибки", "Пример", "Источники"]


def _h2(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, re.M)]


def test_smoke_structure():
    problems: list[str] = []

    for name in PLAYBOOKS:
        p = ROOT / "playbooks" / f"{name}.md"
        if not p.exists():
            problems.append(f"нет playbooks/{name}.md")
            continue
        heads = _h2(p.read_text(encoding="utf-8"))
        need = COMMON + (["Точка человека"] if name in HUMAN_POINT else [])
        problems += [f"playbooks/{name}.md: нет раздела «{h}»" for h in need if h not in heads]
        if name not in HUMAN_POINT and "Точка человека" in heads:
            problems.append(f"playbooks/{name}.md: лишний раздел «Точка человека»")

    for p in sorted((ROOT / "methods").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if not re.match(r"# \S", text):
            problems.append(f"methods/{p.name}: нет заголовка H1 первой строкой")
        heads = _h2(text)
        problems += [f"methods/{p.name}: нет раздела «{h}»" for h in METHOD_H2 if h not in heads]

    agents = ROOT / "AGENTS.md"
    agents_text = agents.read_text(encoding="utf-8") if agents.exists() else ""
    for p in sorted((ROOT / "tools").glob("*.py")):
        if '__name__ == "__main__"' in p.read_text(encoding="utf-8") and f"tools/{p.name}" not in agents_text:
            problems.append(f"AGENTS.md не упоминает tools/{p.name}")

    command_skills = {"status", "new", "continue"}  # навыки-команды чата: без своего playbook, ссылаются на AGENTS.md
    for p in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        if p.parent.name in command_skills:
            if "AGENTS.md" not in p.read_text(encoding="utf-8"):
                problems.append(f"{p.parent.name}/SKILL.md (команда) не ссылается на AGENTS.md")
            continue
        refs = re.findall(r"playbooks/([\w-]+\.md)", p.read_text(encoding="utf-8"))
        if not refs or not all((ROOT / "playbooks" / r).exists() for r in refs):
            problems.append(f"{p.parent.name}/SKILL.md не ссылается на существующий playbook")

    assert not problems, "\n".join(problems)


def test_no_log_human_for_points_in_instructions():
    import re
    for p in list((ROOT / "methods").glob("*.md")) + list((ROOT / "playbooks").glob("*.md")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if "log.py human" in line and re.search(r"точк", line, re.I) and "не вызывай" not in line and "не точка" not in line:
                raise AssertionError(f"{p.name}: точка человека через log.py human (двойной счёт): {line[:80]}")
