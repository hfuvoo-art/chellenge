# Тесты общих функций: ловят битую запись UTF-8, неверные id и сломанные хеши до того, как они попадут в состояние проектов.
import re

from tools import common


def test_write_text_atomic_utf8_no_tmp_left(tmp_path):
    p = tmp_path / "a" / "f.txt"
    common.write_text_atomic(p, "Привет ₽")
    assert common.read_text(p) == "Привет ₽"
    common.write_text_atomic(p, "Ещё раз ≥ ё")
    assert common.read_text(p) == "Ещё раз ≥ ё"
    assert list(tmp_path.rglob("*.tmp")) == []


def test_jsonl_roundtrip_cyrillic(tmp_path):
    p = tmp_path / "x.jsonl"
    common.append_jsonl(p, {"текст": "Турция ₽", "n": 1})
    common.append_jsonl(p, {"текст": "ё", "n": 2})
    assert common.read_jsonl(p) == [{"текст": "Турция ₽", "n": 1}, {"текст": "ё", "n": 2}]
    assert "Турция" in common.read_text(p)
    assert common.read_jsonl(tmp_path / "нет.jsonl") == []


def test_next_id():
    assert common.next_id("C", ["C-001", "C-009"]) == "C-010"
    assert common.next_id("C", []) == "C-001"
    assert common.next_id("C", ["C-999"]) == "C-1000"


def test_yaml_roundtrip_and_hashes_and_time(tmp_path):
    p = tmp_path / "d.yaml"
    common.write_yaml_atomic(p, {"имя": "Стратег", "список": [1, 2]})
    assert common.read_yaml(p) == {"имя": "Стратег", "список": [1, 2]}
    assert common.sha256_text("a") == common.sha256_file(_write(tmp_path, "a"))
    assert re.search(r"\+03:00$", common.now_iso())


def _write(tmp_path, s):
    f = tmp_path / "h.txt"
    f.write_bytes(s.encode("utf-8"))
    return f


def test_normalize_url():
    assert common.normalize_url("HTTPS://Example.com:443/a/?utm_source=x&b=1#frag") == "https://example.com/a?b=1"


def test_projects_dir_env_and_project_path(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path))
    assert common.projects_dir() == tmp_path
    (tmp_path / "demo").mkdir()
    (tmp_path / "CURRENT").write_text("demo\n", encoding="utf-8")
    assert common.project_path() == tmp_path / "demo"
    assert common.project_path("demo") == tmp_path / "demo"
