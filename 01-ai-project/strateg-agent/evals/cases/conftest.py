# Фикстуры красной команды: временный проект и помощники для файлов; без них кейсы полезли бы в реальные проекты.
import pytest


@pytest.fixture
def rt_project(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    d = tmp_path / "projects" / "rt"
    d.mkdir(parents=True)
    (d / "state.yaml").write_text("step: {n: 0, name: not-started}\ndone: {}\n", encoding="utf-8")
    return "rt"
