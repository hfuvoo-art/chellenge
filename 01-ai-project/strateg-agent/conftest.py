# Изоляция всех тестов (tests/ и evals/) от живых проектов: без неё pytest пишет события (lock_update, llm test-model) в log.jsonl текущего проекта из projects/CURRENT и портит его учёт ₽.
import pytest


@pytest.fixture(autouse=True)
def _no_live_projects(monkeypatch, tmp_path):
    """По умолчанию каталог проектов — пустая временная папка; tmp_project и тесты со своим каталогом переопределяют её."""
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "_no_projects"))
