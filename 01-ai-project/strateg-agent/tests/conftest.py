# Общие фикстуры тестов (fake_llm, tmp_project): без них тесты полезут в сеть или в реальный .env и реальные проекты.
import os

import pytest
import yaml

from tools import llm

_LLM_PREFIXES = ("LLM_", "CRITIC_", "EXTRACT_", "PRO_", "JUDGE_")


class HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class FakeLLM:
    """Подмена llm._create: отдаёт ответы по очереди (строка, (текст, usage) или исключение)."""

    def __init__(self):
        self.responses: list = []
        self.calls: list[dict] = []
        self.sleeps: list[float] = []

    def add(self, *items):
        self.responses.extend(items)
        return self

    def __call__(self, role, model, messages, temperature, max_tokens):
        self.calls.append({"role": role, "model": model, "messages": messages})
        if not self.responses:
            raise AssertionError("fake_llm: ответы закончились")
        r = self.responses.pop(0)
        if isinstance(r, BaseException):
            raise r
        if isinstance(r, str):
            return r, {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}
        return r


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch, tmp_path):
    """Реальный .env и переменные окружения модели не влияют на тесты."""
    monkeypatch.setattr(llm, "ENV_FILE", tmp_path / "no.env")
    for k in list(os.environ):
        if k.startswith(_LLM_PREFIXES) and k.endswith(("_MODEL", "_API_KEY", "_BASE_URL", "_PROJECT")):
            monkeypatch.delenv(k, raising=False)


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEG_PROJECTS_DIR", str(tmp_path / "projects"))
    d = tmp_path / "projects" / "p1"
    d.mkdir(parents=True)
    (d / "state.yaml").write_text("step: {n: 0, name: not-started}\ndone: {}\n", encoding="utf-8")
    return "p1"


@pytest.fixture
def fake_llm(tmp_path, monkeypatch):
    prices = tmp_path / "prices.yaml"
    prices.write_text(
        yaml.safe_dump({"models": {"test-model": {"input_per_1k_rub": 0.2, "output_per_1k_rub": 0.4}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(llm, "PRICES_PATH", prices)
    for k, v in {
        "LLM_API_KEY": "test-key", "LLM_BASE_URL": "http://fake/v1", "LLM_PROJECT": "folder",
        "EXTRACT_MODEL": "test-model", "PRO_MODEL": "test-model", "CRITIC_MODEL": "test-model",
    }.items():
        monkeypatch.setenv(k, v)
    fake = FakeLLM()
    monkeypatch.setattr(llm, "_create", fake)
    monkeypatch.setattr(llm.time, "sleep", lambda s: fake.sleeps.append(s))
    return fake
