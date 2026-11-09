# Красная команда: подмена правил (rules.lock, check п.11) и утечки ключей; без него незапертые файлы и непокрытые шаблоны ключей остаются невидимыми.
# xfail(strict=True) = дыра подтверждена прогоном 2026-11-09; когда её закроют, тест упадёт «XPASS» и xfail надо снять.
import shutil
from pathlib import Path

import pytest

from tools import check, ingest, lock
from tools.common import ROOT, project_path, read_text

HOLE = pytest.mark.xfail(strict=True, reason="дыра red-team 2026-11-09")
FAKE_YC = "AQVN" + "fakefakefake" + "1234567890abcd"  # выдуманный ключ
FAKE_SK = "sk-" + "FAKEFAKEFAKE" + "1234567890"


@pytest.fixture
def agent_copy(tmp_path):
    """Копия папки агента без .venv/projects; rules.lock пересчитан под копию."""
    dst = tmp_path / "agent"
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".venv", "projects", "__pycache__", ".pytest_cache", ".git"))
    lock.update(dst, "red-team baseline")
    assert lock.verify(dst) == []
    return dst


def _edit(root: Path, rel: str, extra="\n- tamper\n"):
    p = root / rel
    p.write_text(p.read_text(encoding="utf-8") + extra, encoding="utf-8")


# ---------- держит ----------

@pytest.mark.parametrize("rel", ["rules/evidence.md", "rules/safety.md", "rules/injection-patterns.yaml", "prompts/extract.md",
                                 "AGENTS.md", "tools/check.py", "tools/lock.py"])
def test_locked_file_edit_detected(agent_copy, rel):
    _edit(agent_copy, rel)
    assert any(rel in x for x in lock.verify(agent_copy))
    assert [f.level for f in check.check_lock(agent_copy)] == ["FAIL"]  # проверка 11


def test_new_and_deleted_locked_files_detected(agent_copy):
    (agent_copy / "prompts" / "new.md").write_text("x", encoding="utf-8")
    (agent_copy / "rules" / "style.md").unlink()
    probs = " ".join(lock.verify(agent_copy))
    assert "новый: prompts/new.md" in probs and "удалён: rules/style.md" in probs


def test_missing_rules_lock_fails(agent_copy):
    (agent_copy / "rules.lock").unlink()
    assert lock.verify(agent_copy) and check.check_lock(agent_copy)[0].level == "FAIL"


def test_update_requires_reason(agent_copy):
    with pytest.raises(ValueError):
        lock.update(agent_copy, "  ")


def test_check11_flags_key_in_materials_without_echoing_it(rt_project, tmp_path):
    f = tmp_path / "k.txt"
    f.write_text(f"Price 100 rub\n\nkey {FAKE_YC}\n", encoding="utf-8")
    ingest.ingest(rt_project, str(f), found_by="user")
    res = [x for x in check.check_secrets(project_path(rt_project)) if x.level == "FAIL"]
    assert res and all(FAKE_YC not in (x.msg + x.hint + x.target) for x in res)


def test_llm_error_does_not_leak_key(rt_project, monkeypatch):
    from tools import llm
    monkeypatch.setenv("LLM_API_KEY", FAKE_SK)
    monkeypatch.setenv("LLM_BASE_URL", "http://fake/v1")
    monkeypatch.setenv("EXTRACT_MODEL", "m")

    def boom(*a, **k):
        raise RuntimeError(f"401 Authorization: Bearer {FAKE_SK}")
    monkeypatch.setattr(llm, "_create", boom)
    with pytest.raises(llm.LLMUnavailable) as e:
        llm.chat([{"role": "user", "content": "x"}], role="extract", slug=rt_project)
    assert FAKE_SK not in str(e.value)
    log = project_path(rt_project) / "log.jsonl"
    assert not log.is_file() or FAKE_SK not in read_text(log)


@pytest.mark.parametrize("secret", [FAKE_YC, FAKE_SK, "Bearer " + "abc123def456ghi789jkl"])
def test_secret_shapes_caught(tmp_path, secret):
    p = tmp_path / "s.txt"
    p.write_text(f"x {secret} y\n", encoding="utf-8")
    assert any(f.level == "FAIL" for f in check.check_secrets(p))


# ---------- дыры ----------

@pytest.mark.parametrize("rel", ["methods/jtbd.md", "CLAUDE.md"])
def test_methods_and_claude_md_edit_detected(agent_copy, rel):
    """Закрыто 11.11: методики и CLAUDE.md под замком."""
    _edit(agent_copy, rel, "\n# tamper\n")
    assert lock.verify(agent_copy)


@pytest.mark.parametrize("rel", ["tools/ingest.py", "tools/claims.py", "tools/tables.py", "config/prices.yaml"])
@HOLE
def test_unlocked_file_edit_should_be_detected(agent_copy, rel):
    """Файлы вне LOCKED_*: ingest.py (паттерны и маркеры), claims.py (кто пишет fact) подменяются незаметно; запереть при заморозке фич (задача 21)."""
    _edit(agent_copy, rel, "\n# tamper\n")
    assert lock.verify(agent_copy)


@HOLE
def test_lock_verify_cannot_be_neutered_with_check_py_in_same_tree(agent_copy):
    """lock.py и check.py проверяют сами себя: подмена lock.verify -> [] вместе с правкой правил проходит (rules.lock не пересчитан)."""
    _edit(agent_copy, "rules/safety.md")
    p = agent_copy / "tools" / "lock.py"
    src = p.read_text(encoding="utf-8")
    p.write_text(src.replace('return _diff(_load(root).get("files") or {}, compute(root))', "return []"), encoding="utf-8")
    import importlib.util
    spec = importlib.util.spec_from_file_location("lock_tampered", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.verify(agent_copy)  # ожидание: подмену видно; сейчас пусто


@pytest.mark.parametrize("secret", [
    "bearer " + "abc123def456ghi789jkl",                      # заголовок в нижнем регистре
    "t1." + "9euelZq" + "x" * 40,                             # IAM-токен Yandex Cloud
    "y0_AgAAAAA" + "x" * 30,                                  # OAuth-токен Яндекса
    "AQVN" + "abcdefgh​ijklmnopqrst",                    # ключ с символом нулевой ширины
    "LLM_API_KEY=" + "abc123secretvalue",                     # присваивание переменной окружения
])
@HOLE
def test_secret_shapes_should_be_caught(tmp_path, secret):
    p = tmp_path / "s.txt"
    p.write_text(f"x {secret} y\n", encoding="utf-8")
    assert any(f.level == "FAIL" for f in check.check_secrets(p))


@HOLE
def test_ingest_does_not_copy_key_into_sources_yaml_title(rt_project, tmp_path):
    """Заголовок источника = первая строка текста: ключ из материала дублируется в sources.yaml."""
    f = tmp_path / "k.txt"
    f.write_text(f"Note: key {FAKE_YC}\n\nPrice 100 rub\n", encoding="utf-8")
    ingest.ingest(rt_project, str(f), found_by="user")
    assert FAKE_YC not in read_text(project_path(rt_project) / "sources.yaml")


@HOLE
def test_ingest_does_not_store_token_from_url_query(rt_project, tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("Page about price 5 rub", encoding="utf-8")
    ingest.ingest(rt_project, str(f), found_by="user", url="http://example.test/p?api_key=" + FAKE_YC)
    assert FAKE_YC not in read_text(project_path(rt_project) / "sources.yaml")
